import numpy as np
from scipy.signal import savgol_filter

class RepetitionCounter:
    def __init__(self, exercise_name, metric_configs, ref_thresholds, min_rep_frames=5):
        self.exercise_name = exercise_name
        self.metric_configs = metric_configs
        self.ref_thresholds = ref_thresholds
        self.min_rep_frames = min_rep_frames
        
        self.history = []  # To store the angles of each frame

        # TACTICAL OVERRIDES: Define joint blends for better stability (from notebook)
        self.overrides = {
            'deadlift':                         ['HIP_EXTENSION', 'KNEE_ANGLE'],
            'dumbbell_overhead_shoulder_press': ['SHOULDER_ABDUCTION'],
            'neutral_overhead_shoulder_press':  ['SHOULDER_ABDUCTION'],
            'diamond_pushup':                   ['ELBOW_ANGLE'] 
        }
        
        selected_metrics = self.overrides.get(exercise_name, [list(metric_configs.keys())[0]] if metric_configs else [None])
        t_factor = 0.15 if exercise_name == 'diamond_pushup' else 0.25
        
        self.metrics_data = []
        for m in selected_metrics:
            if m not in metric_configs: continue
            rmin = ref_thresholds.get(f"{m}_min")
            rmax = ref_thresholds.get(f"{m}_max")
            
            if (rmin is None or rmax is None) and m == 'SHOULDER_ABDUCTION':
                rmin, rmax = 80.0, 160.0
                
            if rmin is not None and rmax is not None:
                self.metrics_data.append((m, rmin + t_factor * (rmax - rmin), rmax - t_factor * (rmax - rmin)))
                
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
        """Computes count using variance-weighted signal blending and snapping to peaks."""
        if not self.metrics_data or len(self.history) < 10: return 0
            
        combined_angles = None
        total_weight = 0
        
        for (m, rep_low, rep_high) in self.metrics_data:
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
        _, rep_low, rep_high = self.metrics_data[0] # Thresholds from primary metric
        
        pred_bounds = self._detect_rep_boundaries(angles, rep_low, rep_high)
        return max(0, len(pred_bounds) - 1)
        
    def _detect_rep_boundaries(self, angles, rep_low, rep_high):
        """Hybrid AIFit + Heuristic segmentation with Continuous Domain Relaxation."""
        valid_mask = ~np.isnan(angles)
        if valid_mask.sum() < 10: return []

        interp_angles = angles.copy()
        if not valid_mask.all():
            idx = np.where(valid_mask)[0]
            interp_angles = np.interp(np.arange(len(angles)), idx, angles[valid_mask])

        win = max(3, min(11, int(valid_mask.sum() / 4) * 2 + 1))
        try:
            smoothed = savgol_filter(interp_angles, win, 2)
        except Exception:
            smoothed = interp_angles

        # 1. Dual-Hysteresis State Machine
        state = 0 if smoothed[0] > rep_high else 1
        toggles = []
        for i in range(1, len(smoothed)):
            val = smoothed[i]
            if state == 0 and val < rep_low:
                state = 1; toggles.append(i)
            elif state == 1 and val > rep_high:
                state = 0; toggles.append(i)

        if len(toggles) < 2: return []

        # 2. Extract completed repetitions
        rough_boundaries = [toggles[i] for i in range(1, len(toggles), 2)]

        # 3. Continuous Domain Relaxation: Snap to local extrema
        refined_boundaries = [0]
        search_start = max(0, toggles[0] - 40)
        refined_boundaries[0] = search_start + np.argmax(smoothed[search_start:toggles[0]+1])

        for b in rough_boundaries:
            search_end = min(len(smoothed) - 1, b + 40)
            local_peak = b + np.argmax(smoothed[b:search_end+1])
            refined_boundaries.append(local_peak)

        return sorted(list(set(refined_boundaries)))
