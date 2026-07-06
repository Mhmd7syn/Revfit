import numpy as np
from scipy.signal import savgol_filter

class RepetitionCounter:
    def __init__(self, exercise_name, metric_configs, ref_thresholds):
        self.exercise_name = exercise_name
        self.metric_configs = metric_configs
        self.ref_thresholds = ref_thresholds
        
        self.history = []  # To store the angles of each frame
        self.max_rep_count = 0

        # TACTICAL OVERRIDES: Define joint blends for better stability (from notebook)
        self.overrides = {
            'deadlift':                         ['HIP_EXTENSION', 'KNEE_ANGLE'],
            'dumbbell_overhead_shoulder_press': ['SHOULDER_ABDUCTION'],
            'neutral_overhead_shoulder_press':  ['SHOULDER_ABDUCTION'],
            'diamond_pushup':                   ['ELBOW_ANGLE'] 
        }
        
        selected_metrics = self.overrides.get(exercise_name, [list(metric_configs.keys())[0]] if metric_configs else [None])
        
        self.metrics_data = []
        for m in selected_metrics:
            if m not in metric_configs: continue
            rmin = ref_thresholds.get(f"{m}_min")
            rmax = ref_thresholds.get(f"{m}_max")
            
            if (rmin is None or rmax is None) and m == 'SHOULDER_ABDUCTION':
                rmin, rmax = 80.0, 160.0
                
            if rmin is not None and rmax is not None:
                # Store the raw config bounds — hysteresis thresholds will be
                # derived adaptively from the observed signal range in get_rep_count().
                self.metrics_data.append((m, rmin, rmax))
                
    def add_frame(self, current_metrics, active_sides):
        """Adds current frame metrics to history."""
        frame_data = {}
        for (m, _, _) in self.metrics_data:
            vals = []
            for side in active_sides:
                key = f"{m}_{side.lower()}"
                if key in current_metrics and current_metrics[key] is not None:
                    vals.append(current_metrics[key])
            frame_data[m] = np.mean(vals) if vals else np.nan
        self.history.append(frame_data)
        
    def get_rep_count(self):
        """Computes count using variance-weighted signal blending.

        Hysteresis thresholds are derived adaptively from the *observed* signal
        range rather than the config form-validity bounds (which describe the
        entire safe range of motion, not the actual range traversed in the video).
        """
        if not self.metrics_data or len(self.history) < 10: return 0
            
        combined_angles = None
        total_weight = 0
        
        for (m, rmin, rmax) in self.metrics_data:
            angles = np.array([frame.get(m, np.nan) for frame in self.history])
            if np.isnan(angles).all(): continue
                
            # Weight by Variance (Active vs Passive mining)
            weight = np.nanvar(angles)
            if np.isnan(weight) or weight < 1e-4: weight = 1.0
                
            if combined_angles is None:
                combined_angles = angles * weight
            else:
                combined_angles += angles * weight
            total_weight += weight
            
        if combined_angles is None or total_weight == 0: return 0
            
        angles = combined_angles / total_weight

        # ── Adaptive hysteresis thresholds ──────────────────────────────────
        # Derive rep_low / rep_high from the *actual* signal range observed so
        # far, not from the config bounds.  The config bounds represent the full
        # safe range-of-motion (e.g. knee 30–175° for squats) which is far wider
        # than what any single video clip covers.  Using 25%/75% percentiles of
        # the observed signal gives us thresholds that sit inside the real motion
        # arc regardless of exercise or depth.
        valid = angles[~np.isnan(angles)]
        obs_min = float(np.percentile(valid, 10))
        obs_max = float(np.percentile(valid, 90))
        obs_range = obs_max - obs_min

        # Only run counting if there is meaningful movement (at least 15°).
        if obs_range < 15.0:
            return self.max_rep_count

        # Hysteresis band: 30% of the observed range inward from each extreme.
        # This means the signal must travel past 30% of its actual motion arc
        # before a state change fires — robust against small oscillations.
        hysteresis = 0.30 * obs_range
        rep_low  = obs_min + hysteresis   # low-end crossing threshold
        rep_high = obs_max - hysteresis   # high-end crossing threshold

        pred_bounds = self._detect_rep_boundaries(angles, rep_low, rep_high)
        current_count = max(0, len(pred_bounds) - 1)
        
        # Enforce monotonicity to prevent flickering during movement
        if current_count > self.max_rep_count:
            self.max_rep_count = current_count
            
        return self.max_rep_count
        
    def _detect_rep_boundaries(self, angles, rep_low, rep_high):
        """Hybrid AIFit + Heuristic segmentation with Continuous Domain Relaxation."""
        valid_mask = ~np.isnan(angles)
        if valid_mask.sum() < 10: return []

        interp_angles = angles.copy()
        if not valid_mask.all():
            idx = np.where(valid_mask)[0]
            interp_angles = np.interp(np.arange(len(angles)), idx, angles[valid_mask])

        # Window must be odd, ≥3, <len(signal), and reasonable (3–11)
        n_valid = int(valid_mask.sum())
        win = max(3, min(11, (n_valid // 4) * 2 + 1))
        # Ensure window < signal length (required by savgol_filter)
        win = min(win, len(interp_angles) - (1 if len(interp_angles) % 2 == 0 else 0))
        if win < 3 or win >= len(interp_angles):
            smoothed = interp_angles
        else:
            try:
                smoothed = savgol_filter(interp_angles, win, 2)
            except Exception:
                smoothed = interp_angles

        # Minimum frames between toggles to reject noise-induced micro-transitions.
        # A real rep takes at least ~4 processed frames (≈0.5s at 30fps, frame_skip=2).
        min_toggle_gap = max(4, n_valid // 20)

        # 1. Determine initial state robustly using a short look-ahead window
        #    to avoid misclassifying a mid-motion first frame as the resting state.
        look_ahead = min(5, len(smoothed))
        first_val = float(np.nanmedian(smoothed[:look_ahead]))

        # State 0 = "high" (above rep_high, i.e. at top/extended position)
        # State 1 = "low"  (below rep_low,  i.e. at bottom/contracted position)
        # If signal is between the thresholds at the start, we pick the state
        # that requires the *least* movement to reach the first threshold.
        if first_val > rep_high:
            state = 0  # starts at top
        elif first_val < rep_low:
            state = 1  # starts at bottom
        else:
            # Mid-range start: infer from which threshold is closer
            state = 0 if (first_val - rep_low) > (rep_high - first_val) else 1

        # Track whether the signal started "high" (for boundary refinement direction)
        started_high = (state == 0)

        toggles = []
        last_toggle_idx = -min_toggle_gap  # allow a toggle from the very first frame
        for i in range(1, len(smoothed)):
            val = smoothed[i]
            # Enforce minimum gap between consecutive toggles
            if (i - last_toggle_idx) < min_toggle_gap:
                continue
            if state == 0 and val < rep_low:
                state = 1
                toggles.append(i)
                last_toggle_idx = i
            elif state == 1 and val > rep_high:
                state = 0
                toggles.append(i)
                last_toggle_idx = i

        if len(toggles) < 2: return []

        # 2. Extract completed repetitions.
        #    A full rep is: start_state → crossed one threshold → crossed back.
        #    toggles[0] = first crossing (leaving rest position)
        #    toggles[1] = second crossing (returning to rest position)  ← rep boundary
        #    toggles[2] = leaving again …  etc.
        #
        #    Completed rep boundaries are at every even-indexed toggle (0-based: 1, 3, 5…)
        rough_boundaries = [toggles[i] for i in range(1, len(toggles), 2)]

        if not rough_boundaries:
            return []

        # 3. Continuous Domain Relaxation: Snap boundaries to local extrema.
        #    The initial boundary is the starting "peak" (or trough) before the
        #    first crossing.  Subsequent boundaries snap to the same kind of extremum
        #    (peak if started high, trough if started low).
        search_start = max(0, toggles[0] - 40)

        if started_high:
            # Started at top → snap start boundary to local maximum
            refined_start = search_start + int(np.argmax(smoothed[search_start:toggles[0] + 1]))
        else:
            # Started at bottom → snap start boundary to local minimum
            refined_start = search_start + int(np.argmin(smoothed[search_start:toggles[0] + 1]))

        refined_boundaries = [refined_start]

        for b in rough_boundaries:
            search_end = min(len(smoothed) - 1, b + 40)
            segment = smoothed[b:search_end + 1]
            if started_high:
                # Each rep ends back at the "top" → local maximum
                local_extremum = b + int(np.argmax(segment))
            else:
                # Each rep ends back at the "bottom" → local minimum
                local_extremum = b + int(np.argmin(segment))
            refined_boundaries.append(local_extremum)

        return sorted(list(set(refined_boundaries)))
