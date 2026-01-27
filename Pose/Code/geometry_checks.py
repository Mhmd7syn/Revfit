import numpy as np

class GeometryChecks:
    @staticmethod
    def calculate_distance(p1, p2):
        return np.linalg.norm(np.array(p1) - np.array(p2))

    @staticmethod
    def calculate_horizontal_distance(p1, p2):
        return abs(p1[0] - p2[0])

    @staticmethod
    def calculate_vertical_distance(p1, p2):
        return abs(p1[1] - p2[1])

    @staticmethod
    def calculate_angle(a, b, c):
        """Calculates angle ABC (at point B) in degrees."""
        a = np.array(a)
        b = np.array(b)
        c = np.array(c)
        ba = a - b
        bc = c - b
        cosine_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6)
        angle = np.arccos(np.clip(cosine_angle, -1.0, 1.0))
        return np.degrees(angle)

    @staticmethod
    def distance_from_line(p0, p1, p2):
        """Calculates perpendicular distance of point p0 from line p1-p2."""
        p0 = np.array(p0)
        p1 = np.array(p1)
        p2 = np.array(p2)
        return np.abs(np.cross(p2 - p1, p1 - p0)) / (np.linalg.norm(p2 - p1) + 1e-6)

    @staticmethod
    def check_exercise(exercise_name, keypoints, side='right'):
        """Dispatcher for exercise-specific checks."""
        name = exercise_name.lower()
        
        # Pushing (Horizontal)
        if any(x in name for x in ['bench press']): return GeometryChecks.check_bench_press(name, keypoints, side)
        if 'push-up' in name or 'push up' in name: return GeometryChecks.check_pushup(keypoints, side)
        if 'fly' in name: return GeometryChecks.check_chest_fly(keypoints, side)
        
        # Pushing (Vertical)
        if 'shoulder press' in name: return GeometryChecks.check_shoulder_press(keypoints, side)
        if 'dips' in name: return GeometryChecks.check_dips(keypoints, side)
        
        # Pulling (Vertical)
        if 'lat pulldown' in name: return GeometryChecks.check_lat_pulldown(keypoints, side)
        if 'pull up' in name: return GeometryChecks.check_pullup(keypoints, side)
        
        # Pulling (Horizontal)
        if 'row' in name: return GeometryChecks.check_row(keypoints, side)
        
        # Isolation (Arm)
        if 'curl' in name: return GeometryChecks.check_bicep_curl(keypoints, side)
        if 'tricep pushdown' in name: return GeometryChecks.check_tricep_pushdown(keypoints, side)
        if 'lateral raise' in name: return GeometryChecks.check_lateral_raise(keypoints, side)
        
        # Leg Compound
        if 'squat' in name: return GeometryChecks.check_squat(keypoints, side)
        if 'deadlift' in name and 'romanian' not in name: return GeometryChecks.check_deadlift(keypoints, side)
        if 'romanian' in name: return GeometryChecks.check_rdl(keypoints, side)
        if 'hip thrust' in name: return GeometryChecks.check_hip_thrust(keypoints, side)
        if 'leg extension' in name: return GeometryChecks.check_leg_extension(keypoints, side)
        
        # Core
        if 'plank' in name: return GeometryChecks.check_plank(keypoints, side)
        if 'russian twist' in name: return GeometryChecks.check_russian_twist(keypoints, side)
        if 'leg raises' in name: return GeometryChecks.check_leg_raises(keypoints, side)
        
        return []

    # --- PUSHING EXERCISES ---

    @staticmethod
    def check_bench_press(name, keypoints, side):
        feedback = []
        wrist = keypoints.get('wrist')
        elbow = keypoints.get('elbow')
        
        # Rule 1: Vertical Forearms (Stack)
        if wrist is not None and elbow is not None:
            h_dist = GeometryChecks.calculate_horizontal_distance(wrist, elbow)
            if h_dist > 0.08: # Threshold approx 8% of screen width
                feedback.append(f"[{side}] Stack wrists over elbows (Horizontal drift: {h_dist:.2f})")
                
        return feedback

    @staticmethod
    def check_pushup(keypoints, side):
        feedback = []
        shoulder = keypoints.get('shoulder')
        hip = keypoints.get('hip')
        ankle = keypoints.get('ankle')
        
        # Rule 1: Body Line (Sagging/Piking)
        if shoulder is not None and hip is not None and ankle is not None:
            dist = GeometryChecks.distance_from_line(hip, shoulder, ankle)
            if dist > 0.05:
                feedback.append(f"[{side}] Maintain a straight body line (Deviation: {dist:.2f})")
                
        return feedback

    @staticmethod
    def check_chest_fly(keypoints, side):
        feedback = []
        # Rule 1: Isometric Elbow.
        shoulder = keypoints.get('shoulder')
        elbow = keypoints.get('elbow')
        wrist = keypoints.get('wrist')
        
        if shoulder is not None and elbow is not None and wrist is not None:
            angle = GeometryChecks.calculate_angle(shoulder, elbow, wrist)
            if angle > 170:
                feedback.append(f"[{side}] Keep a clearer bent in elbows to protect joints.")
        return feedback

    @staticmethod
    def check_shoulder_press(keypoints, side):
        feedback = []
        wrist = keypoints.get('wrist')
        elbow = keypoints.get('elbow')
        shoulder = keypoints.get('shoulder')
        
        # Rule 1: Elbow Stack (Keep elbows under wrists)
        if wrist is not None and elbow is not None:
            h_dist = GeometryChecks.calculate_horizontal_distance(wrist, elbow)
            if h_dist > 0.1:
                feedback.append(f"[{side}] Keep elbows under wrists.")
        return feedback

    @staticmethod
    def check_dips(keypoints, side):
        feedback = []
        shoulder = keypoints.get('shoulder')
        elbow = keypoints.get('elbow')
        
        # Rule 1: Excessive Depth
        # Shoulders should not drop significantly below elbows.
        # Y is positive down. Danger: Y_shoulder > Y_elbow + buffer
        if shoulder is not None and elbow is not None:
            if shoulder[1] > elbow[1] + 0.05: 
                feedback.append(f"[{side}] Too deep! Limit depth to protect shoulders.")
        return feedback

    # --- PULLING EXERCISES ---

    @staticmethod
    def check_lat_pulldown(keypoints, side):
        feedback = []
        shoulder = keypoints.get('shoulder')
        hip = keypoints.get('hip')
        
        # Rule 1: Excessive Leaning
        # Use angle relative to vertical to account for camera zoom/body size differences
        if shoulder is not None and hip is not None:
            # Create a point directly above the hip to represent vertical
            vertical_ref = [hip[0], hip[1] - 0.5]
            
            lean_angle = GeometryChecks.calculate_angle(shoulder, hip, vertical_ref)
            
            # Lat pulldown allows slight lean (10-20 deg), warn if significant
            if lean_angle > 30: 
                feedback.append(f"[{side}] Avoid excessive leaning back ({lean_angle:.0f}°).")
        return feedback

    @staticmethod
    def check_pullup(keypoints, side):
        feedback = []
        nose = keypoints.get('nose')
        wrist = keypoints.get('wrist')
        
        # Rule: Chin over bar (Wrist usually proxy for bar)
        if nose is not None and wrist is not None:
            # Check if nose is above wrist (Y_nose < Y_wrist)
            if nose[1] < wrist[1]:
                feedback.append(f"[{side}] GOOD: Chin above bar!")
        return feedback

    @staticmethod
    def check_row(keypoints, side):
        feedback = []
        shoulder = keypoints.get('shoulder')
        hip = keypoints.get('hip')
        nose = keypoints.get('nose')
        
        # Rule 1: Torso Angle (Prevent standing up too much)
        # Angle of Torso (Shoulder-Hip) relative to Vertical
        if shoulder is not None and hip is not None:
             vertical_ref = [hip[0], hip[1] - 0.5] # Point directly above hip
             torso_angle = GeometryChecks.calculate_angle(shoulder, hip, vertical_ref)
             
             # Rows require significant forward lean (usually 30-90 degrees)
             if torso_angle < 30:
                 feedback.append(f"[{side}] Bend over more! Torso too upright ({torso_angle:.0f}°).")
        
        # Rule 2: Neck Alignment (Spine Neutrality Proxy)
        # Check if head is roughly inline with torso
        if nose is not None and shoulder is not None and hip is not None:
             dist = GeometryChecks.distance_from_line(nose, shoulder, hip)
             if dist > 0.15:
                 feedback.append(f"[{side}] Keep neck neutral with spine.")
                 
        return feedback

    # --- ISOLATION ---

    @staticmethod
    def check_bicep_curl(keypoints, side):
        feedback = []
        shoulder = keypoints.get('shoulder')
        elbow = keypoints.get('elbow')
        
        # Rule 1: Elbow Pinning (Horizontal drift)
        if shoulder is not None and elbow is not None:
            h_dist = GeometryChecks.calculate_horizontal_distance(shoulder, elbow)
            if h_dist > 0.1:
                feedback.append(f"[{side}] Pin that elbow! Don't swing shoulder.")
        return feedback
    
    @staticmethod
    def check_tricep_pushdown(keypoints, side):
        feedback = []
        shoulder = keypoints.get('shoulder')
        elbow = keypoints.get('elbow')
        
        # Rule 1: Elbow Pinning (Same as curl)
        if shoulder is not None and elbow is not None:
            h_dist = GeometryChecks.calculate_horizontal_distance(shoulder, elbow)
            if h_dist > 0.1:
                feedback.append(f"[{side}] Keep elbows pinned to sides.")
        return feedback

    @staticmethod
    def check_lateral_raise(keypoints, side):
        feedback = []
        shoulder = keypoints.get('shoulder')
        elbow = keypoints.get('elbow')
        wrist = keypoints.get('wrist')
        
        # Rule 1: Impingement Risk (Elbow above Shoulder)
        # Y increases down. Danger: Y_elbow < Y_shoulder
        if shoulder is not None and elbow is not None:
            if elbow[1] < shoulder[1] - 0.05: 
                feedback.append(f"[{side}] Lower elbows slightly to protect shoulders.")

        # Rule 2: Leading with Wrist (Wrist above Elbow)
        # Wrist should be slightly below or inline with elbow, never significantly above
        if wrist is not None and elbow is not None:
            if wrist[1] < elbow[1] - 0.05:
                feedback.append(f"[{side}] Lead with elbows, not wrists.")
        return feedback

    # --- LEG EXERCISES ---

    @staticmethod
    def check_squat(keypoints, side):
        feedback = []
        hip = keypoints.get('hip')
        knee = keypoints.get('knee')
        
        # Rule 1: Depth
        if hip is not None and knee is not None:
            if hip[1] > knee[1]:
                feedback.append(f"[{side}] GOOD: Parallel/Deep depth hit!")
            elif abs(hip[1] - knee[1]) < 0.05:
                 feedback.append(f"[{side}] Hitting parallel...")
        return feedback

    @staticmethod
    def check_deadlift(keypoints, side):
        feedback = []
        shoulder = keypoints.get('shoulder')
        hip = keypoints.get('hip')
        knee = keypoints.get('knee')
        
        # Rule 1: The Wedge (Hips between Shoulders and Knees)
        # Y increases down. 
        # Correct: Y_shoulder (Smallest) < Y_hip < Y_knee (Largest)
        if shoulder is not None and hip is not None and knee is not None:
            if hip[1] < shoulder[1]:
                feedback.append(f"[{side}] Hips too high! Lower hips to engage legs.")
            elif hip[1] > knee[1]:
                 feedback.append(f"[{side}] Hips too low! Don't squat the deadlift.")
            
        return feedback

    @staticmethod
    def check_rdl(keypoints, side):
        feedback = []
        hip = keypoints.get('hip')
        knee = keypoints.get('knee')
        ankle = keypoints.get('ankle')
        shoulder = keypoints.get('shoulder')
        nose = keypoints.get('nose')

        # Rule 1: Soft Knees (Not locked, not squatting)
        if hip is not None and knee is not None and ankle is not None:
             angle = GeometryChecks.calculate_angle(hip, knee, ankle)
             if angle > 175:
                 feedback.append(f"[{side}] Unlock your knees! Too straight ({angle:.0f}°).")
             elif angle < 140:
                 feedback.append(f"[{side}] Too much knee bend! It's a hinge, not a squat ({angle:.0f}°).")

        # Rule 2: Neck Neutrality
        if nose is not None and shoulder is not None and hip is not None:
             dist = GeometryChecks.distance_from_line(nose, shoulder, hip)
             if dist > 0.15:
                 feedback.append(f"[{side}] Tuck your chin! Keep neck neutral.")

        return feedback

    @staticmethod
    def check_hip_thrust(keypoints, side):
        feedback = []
        shoulder = keypoints.get('shoulder')
        hip = keypoints.get('hip')
        knee = keypoints.get('knee')
        
        # Rule 1: Full Extension
        if shoulder is not None and hip is not None and knee is not None:
            angle = GeometryChecks.calculate_angle(shoulder, hip, knee)
            if angle > 170:
                feedback.append(f"[{side}] GOOD: Full hip extension!")
        return feedback

    @staticmethod
    def check_leg_extension(keypoints, side):
        feedback = []
        hip = keypoints.get('hip')
        knee = keypoints.get('knee')
        ankle = keypoints.get('ankle')
        
        # Rule 1: Full Leg Extension
        # Goal: Angle (Hip-Knee-Ankle) should near 180 degrees at top
        if hip is not None and knee is not None and ankle is not None:
            angle = GeometryChecks.calculate_angle(hip, knee, ankle)
            if angle < 150:
                 feedback.append(f"[{side}] Extend fully! Squeeze quads ({angle:.0f}°).")
            elif angle > 170:
                 feedback.append(f"[{side}] GOOD: Full extension!")
        return feedback

    # --- CORE ---

    @staticmethod
    def check_plank(keypoints, side):
        feedback = []
        shoulder = keypoints.get('shoulder')
        hip = keypoints.get('hip')
        ankle = keypoints.get('ankle')
        
        if shoulder is not None and hip is not None and ankle is not None:
            dist = GeometryChecks.distance_from_line(hip, shoulder, ankle)
            if dist > 0.05:
                feedback.append(f"[{side}] Align hips with body (Dev: {dist:.2f})")
        return feedback

    @staticmethod
    def check_russian_twist(keypoints, side):
        feedback = []
        shoulder = keypoints.get('shoulder')
        hip = keypoints.get('hip')
        knee = keypoints.get('knee')
        
        # Rule 1: V-Sit Angle
        # Torso should clear floor (Angle Shoulder-Hip-Knee)
        # Typically around 90-135 degrees depending on difficulty
        if shoulder is not None and hip is not None and knee is not None:
            angle = GeometryChecks.calculate_angle(shoulder, hip, knee)
            if angle > 150:
                feedback.append(f"[{side}] Lean back less! Engage core more ({angle:.0f}°).")
            elif angle < 70:
                 feedback.append(f"[{side}] Don't sit up too completely! Lean back slightly.")
        return feedback

    @staticmethod
    def check_leg_raises(keypoints, side):
        feedback = []
        hip = keypoints.get('hip')
        knee = keypoints.get('knee')
        ankle = keypoints.get('ankle')
        
        # Rule 1: Straight Legs
        # Improve lever arm by keeping legs straight
        if hip is not None and knee is not None and ankle is not None:
            angle = GeometryChecks.calculate_angle(hip, knee, ankle)
            if angle < 150:
                feedback.append(f"[{side}] Keep legs straighter! ({angle:.0f}°).")
        return feedback
