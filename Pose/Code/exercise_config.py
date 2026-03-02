# Format: { 'names': [...], 'type': 'angle'|'horizontal_distance'|'vertical_distance'|'distance_from_line', 'joints': [...] }
_JOINT_GROUPS = {
    # --- ANGLES ---
    ('ELBOW_ANGLE', 'ELBOW_BEND', 'ARM_BEND'): {
        'type': 'angle',
        'joints': ['shoulder', 'elbow', 'wrist'],
        'message_high': 'Elbows too straight.',
        'message_low': 'Elbows bent too much.'
    },
    ('KNEE_ANGLE', 'LEG_STRAIGHTNESS', 'SOFT_KNEES'): {
        'type': 'angle',
        'joints': ['hip', 'knee', 'ankle'],
        'message_high': 'Legs too straight (Lockout?).',
        'message_low': 'Bend knees less.'
    },
    ('HIP_EXTENSION', 'TORSO_STABILITY'): {
        'type': 'angle',
        'joints': ['shoulder', 'hip', 'knee'],
        'message_high': 'Hips extended too much.',
        'message_low': 'Hips flexed too much (sitting back?).'
    },
    ('SHOULDER_ABDUCTION', 'ELBOW_FLARE'): {
        'type': 'angle',
        'joints': ['hip', 'shoulder', 'elbow'],
        'message_high': 'Elbows flaring out too much.'
    },
    ('SHIN_ANGLE',): {
        'type': 'angle',
        'joints': ['vertical', 'ankle', 'knee'],
        'message_high': 'Knees tracking too far forward.'
    },
    ('TORSO_SWING', 'TORSO_LEAN', 'TORSO_ARCH', 'BACK_ANGLE_VERTICAL'): {
        'type': 'angle',
        'joints': ['vertical', 'hip', 'shoulder'],
        'message_high': 'Excessive torso lean (swinging or arching).',
        'message_low': 'Torso too upright.'
    },
    ('BACK_ANGLE_HORIZONTAL',): {
        'type': 'angle',
        'joints': ['horizontal', 'hip', 'shoulder'],
        'message_high': 'Torso too upright.',
        'message_low': 'Torso too low.'
    },
    ('BODY_SWING',): {
        'type': 'angle',
        'joints': ['shoulder', 'hip', 'vertical'], 
        'message_high': 'Excessive body swing (keep still).'
    },

    # --- HORIZONTAL DISTANCES ---
    ('SHOULDER_SWING', 'ELBOW_PIN', 'ELBOW_STABILITY'): {
        'type': 'horizontal_distance',
        'joints': ['shoulder', 'elbow'],
        'message_high': 'Keep elbows pinned to your sides (Horizontal Drift)!'
    },
    ('WRIST_ELBOW_STACK',): {
        'type': 'horizontal_distance',
        'joints': ['wrist', 'elbow'],
        'message_high': 'Stack wrists over elbows (Horizontal Drift).'
    },

    # --- VERTICAL DISTANCES ---
    ('SHOULDER_ELBOW_DEPTH',): {
        'type': 'vertical_distance',
        'joints': ['shoulder', 'elbow'],
        'message_high': 'Too deep! Shoulders dropping below elbows.'
    },
    ('IMPINGEMENT_RISK',): {
         'type': 'vertical_distance',
         'joints': ['elbow', 'shoulder'],
         'message_low': 'Lower elbows slightly to protect shoulders.'
    },
    ('WRIST_ELBOW_HEIGHT',): {
        'type': 'vertical_distance',
        'joints': ['wrist', 'elbow'],
        'message_low': 'Lead with elbows, not wrists.'
    },
    ('CHIN_BAR_HEIGHT',): {
        'type': 'vertical_distance',
        'joints': ['nose', 'wrist'],
        'message_high': 'Get your chin over the bar!' 
    },
    ('HIP_SHOULDER_HEIGHT',): {
        'type': 'vertical_distance',
        'joints': ['hip', 'shoulder'],
        'message_low': 'Hips too high! Lower hips.'
    },
    ('HIP_KNEE_HEIGHT_DEADLIFT',): {
        'type': 'vertical_distance',
        'joints': ['hip', 'knee'],
        'message_high': 'Hips too low! Don\'t squat the deadlift.' 
    },
    ('SQUAT_DEPTH_CHECK',): {
        'type': 'vertical_distance',
        'joints': ['hip', 'knee'],
        'message_high': 'Squatting too deep (past safe limit)!'
    },

    # --- DISTANCE FROM LINE ---
    ('BODY_LINE', 'HIP_SAG', 'HIP_HIKE'): {
        'type': 'distance_from_line',
        'joints': ['hip', 'shoulder', 'ankle'],
        'message_high': 'Body not straight (Sagging or Piking).'
    },
    ('NECK_ALIGNMENT',): {
        'type': 'distance_from_line',
        'joints': ['nose', 'shoulder', 'hip'],
        'message_high': 'Keep neck neutral with spine.'
    },
    ('HIP_ALIGNMENT',): {
        'type': 'distance_from_line',
        'joints': ['hip', 'shoulder', 'ankle'],
        'message_high': 'Align hips with body.'
    }
}

# Flatten into the lookup dictionary
JOINT_DEFINITIONS = {name: config for names, config in _JOINT_GROUPS.items() for name in names}

# Group exercises with identical configurations
_EXERCISE_GROUPS = {
    ('barbell biceps curl', 'hammer curl'): ['ELBOW_ANGLE', 'ELBOW_PIN', 'TORSO_SWING'],
    ('romanian deadlift',): ['HIP_EXTENSION', 'SOFT_KNEES', 'NECK_ALIGNMENT'],
    ('deadlift',): ['HIP_EXTENSION', 'KNEE_ANGLE', 'HIP_SHOULDER_HEIGHT', 'HIP_KNEE_HEIGHT_DEADLIFT', 'NECK_ALIGNMENT'],
    ('incline bench press', 'decline bench press', 'bench press'): ['ELBOW_ANGLE', 'ELBOW_FLARE', 'WRIST_ELBOW_STACK'],
    ('chest fly machine',): ['ELBOW_BEND', 'SHOULDER_ABDUCTION'],
    ('hip thrust',): ['HIP_EXTENSION', 'SHIN_ANGLE'],
    ('lat pulldown',): ['ELBOW_ANGLE', 'TORSO_SWING'],
    ('lateral raise',): ['SHOULDER_ABDUCTION', 'ELBOW_BEND', 'IMPINGEMENT_RISK', 'WRIST_ELBOW_HEIGHT'],
    ('leg extension',): ['KNEE_ANGLE', 'TORSO_STABILITY'],
    ('leg raises',): ['HIP_EXTENSION', 'LEG_STRAIGHTNESS'],
    ('plank',): ['BODY_LINE'],
    ('pull up',): ['ELBOW_ANGLE', 'BODY_SWING', 'CHIN_BAR_HEIGHT'],
    ('push-up',): ['ELBOW_ANGLE', 'ELBOW_FLARE', 'BODY_LINE'],
    ('russian twist',): ['HIP_EXTENSION', 'TORSO_LEAN'],
    ('shoulder press',): ['ELBOW_ANGLE', 'TORSO_ARCH', 'WRIST_ELBOW_STACK'],
    ('squat',): ['HIP_EXTENSION', 'KNEE_ANGLE', 'BACK_ANGLE_VERTICAL', 'SQUAT_DEPTH_CHECK'],
    ('t bar row',): ['ELBOW_ANGLE', 'BACK_ANGLE_HORIZONTAL', 'SOFT_KNEES', 'NECK_ALIGNMENT'],
    ('tricep dips',): ['ELBOW_ANGLE', 'TORSO_LEAN', 'SHOULDER_ELBOW_DEPTH'],
    ('tricep pushdown',): ['ELBOW_ANGLE', 'ELBOW_PIN', 'TORSO_SWING']
}

# Flatten into map
EXERCISE_TO_CONFIG = {ex: conf for exercises, conf in _EXERCISE_GROUPS.items() for ex in exercises}
