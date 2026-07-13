# Fit3D 25-joint skeleton mapping (Indices for Left, Right)
FIT3D_JOINT_MAP = {
    'hip':        (1, 4),
    'knee':       (2, 5),
    'ankle':      (3, 6),
    'shoulder':   (11, 14),
    'elbow':      (12, 15),
    'wrist':      (13, 16),
    'index':      (18, 21),
    'nose':       None,  # Fit3D neck (10) can be used as a proxy if needed
    'vertical':   None,
    'horizontal': None,
}

# Mapping from Fit3D action names to internal config names
FIT3D_TO_CONFIG_NAME = {
    'squat':                           'squat',
    'deadlift':                        'deadlift',
    'pushup':                          'push-up',
    'diamond_pushup':                  'push-up',
    'dumbbell_biceps_curls':           'barbell biceps curl',
    'dumbbell_hammer_curls':           'hammer curl',
    'dumbbell_overhead_shoulder_press':'shoulder press',
    'neutral_overhead_shoulder_press': 'shoulder press',
    'side_lateral_raise':              'lateral raise',
    'dumbbell_scaptions':              'lateral raise',
    'man_maker':                       'burpee_variant',
    'clean_and_press':                 'clean_and_press',
    'burpees':                         'burpee',
    'overhead_extension_thruster':     'thruster',
}

# Format: { 'names': [...], 'type': 'angle'|'horizontal_distance'|'vertical_distance'|'distance_from_line', 'joints': [...] }
_JOINT_GROUPS = {
    # --- ANGLES ---
    ('ELBOW_ANGLE', 'ELBOW_BEND', 'ARM_BEND'): {
        'type': 'angle',
        'joints': ['shoulder', 'elbow', 'wrist'],
        'message_high': 'Elbows too straight.',
        'message_low': 'Elbows bent too much.',
        'hard_max': 175.0  # Beighton Hypermobility Score (Ehlers-Danlos Society, current criteria): elbow hyperextension >10° flags joint hypermobility; 175° prevents loading into that range
    },
    ('WRIST_ANGLE',): {
        'type': 'angle',
        'joints': ['elbow', 'wrist', 'index'],
        'message_low': 'Keep wrists straight. Do not curl or extend them.',
        'tolerance': 10.0  # IMU wrist kinematics (Frontiers in Bioengineering, 2022): flexion/extension measurement errors of 4–12°; ±10° reflects the achievable neutral-zone precision for markerless systems
    },
    ('KNEE_ANGLE', 'LEG_STRAIGHTNESS', 'SOFT_KNEES'): {
        'type': 'angle',
        'joints': ['hip', 'knee', 'ankle'],
        'message_high': 'Legs too straight (Lockout?).',
        'message_low': 'Bend knees less.',
        'hard_max': 175.0  # Beighton Hypermobility Score (Ehlers-Danlos Society, current criteria): knee hyperextension >10° flags joint hypermobility; 175° prevents loading into that range
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
        'message_high': 'Elbows flaring out too much.',
        'tolerance': 15.0  # Mercadal-Baudart et al. (2024): shoulder RMS errors are within 15° (larger than trunk/lower-body metrics)
    },
    ('SHIN_ANGLE',): {
        'type': 'angle',
        'joints': ['vertical', 'ankle', 'knee'],
        'message_high': 'Knees tracking too far forward.'
    },
    ('TORSO_SWING', 'TORSO_LEAN', 'TORSO_ARCH', 'BODY_SWING'): {
        'type': 'angle',
        'joints': ['vertical', 'hip', 'shoulder'],
        'message_high': 'Excessive torso lean (swinging or arching).',
        'tolerance': 10.0  # Mercadal-Baudart et al. (2024): trunk angle RMS errors are within 10° for most exercises
    },
    ('BACK_ANGLE_VERTICAL',): {
        'type': 'angle',
        'joints': ['vertical', 'hip', 'shoulder'],
        'message_high': 'Excessive forward lean.',
        'message_low': 'Torso too upright.',
        'tolerance': 10.0  # Mercadal-Baudart et al. (2024): trunk/spinal angle RMS errors are within 10° across fitness exercises
    },
    ('BACK_ANGLE_HORIZONTAL',): {
        'type': 'angle',
        'joints': ['horizontal', 'hip', 'shoulder'],
        'message_high': 'Torso too upright.',
        'message_low': 'Torso too low.',
        'tolerance': 15.0  # Mercadal-Baudart et al. (2024): shoulder/ASIS metrics are within 15°; 2D camera has higher error in horizontal plane
    },


    # --- HORIZONTAL DISTANCES ---
    ('SHOULDER_SWING', 'ELBOW_PIN', 'ELBOW_STABILITY'): {
        'type': 'horizontal_distance',
        'joints': ['shoulder', 'elbow'],
        'message_high': 'Keep elbows pinned to your sides (Horizontal Drift)!',
        'tolerance': 0.05  # Mercadal-Baudart et al. (2024): ~5% normalized distance is within expected MediaPipe landmark noise for upper limb
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
        'message_high': 'Body not straight (Sagging or Piking).',
        'tolerance': 0.08  # Mercadal-Baudart et al. (2024): hip depth ambiguity in single-camera setups; 8% baseline absorbs depth noise before heuristic rules fire
    },
    ('NECK_ALIGNMENT',): {
        'type': 'distance_from_line',
        'joints': ['nose', 'shoulder', 'hip'],
        'message_high': 'Keep neck neutral with spine.',
        'tolerance': 0.15  # Mercadal-Baudart et al. (2024): facial landmarks (nose) are highly susceptible to jitter in single-camera setups; 15% torso-length tolerance prevents false positives from head orientation drift
    },
    ('HIP_ALIGNMENT',): {
        'type': 'distance_from_line',
        'joints': ['hip', 'shoulder', 'ankle'],
        'message_high': 'Align hips with body.',
        'tolerance': 0.08  # Mercadal-Baudart et al. (2024): hip as middle point in line-distance is most affected by depth estimation error in single-lens setups
    }
}

# Flatten into the lookup dictionary
JOINT_DEFINITIONS = {name: config for names, config in _JOINT_GROUPS.items() for name in names}

# Group exercises with distinct configurations using official NASM and NSCA metrics.
# NOTE: The FIRST angle-type metric in each list is the primary rep-counting metric.
_EXERCISE_GROUPS = {
    ('barbell biceps curl', 'hammer curl'): {
        'metrics': ['ELBOW_ANGLE', 'ELBOW_PIN', 'TORSO_SWING', 'ELBOW_FLARE', 'WRIST_ANGLE'],
        'thresholds': {
            'ELBOW_ANGLE_min': 30.0, 'ELBOW_ANGLE_max': 160.0,
            'ELBOW_PIN_min': 0.0, 'ELBOW_PIN_max': 0.15,  # NASM: elbows stay within ~15% torso-width of sides
            'TORSO_SWING_min': 0.0, 'TORSO_SWING_max': 80.0,  # NASM: catches only severe swinging; 2D-projected lean regularly exceeds 50° due to off-axis camera placement
            'ELBOW_FLARE_min': 0.0, 'ELBOW_FLARE_max': 45.0,  # NASM: elbow angle from torso should stay <45°
            'WRIST_ANGLE_min': 85.0, 'WRIST_ANGLE_max': 180.0,  # NASM: neutral wrist; relaxed since wrist naturally dips during supination
        },
        'source': "NASM Compensations: Avoid torso swing and elbow flare. Keep wrists neutral."
    },
    ('squat',): {
        'metrics': ['KNEE_ANGLE', 'HIP_EXTENSION', 'BACK_ANGLE_VERTICAL', 'SQUAT_DEPTH_CHECK'],
        'thresholds': {
            'KNEE_ANGLE_min': 30.0, 'KNEE_ANGLE_max': 175.0,
            'HIP_EXTENSION_min': 30.0, 'HIP_EXTENSION_max': 175.0,
            'BACK_ANGLE_VERTICAL_min': 5.0, 'BACK_ANGLE_VERTICAL_max': 95.0,
            'SQUAT_DEPTH_CHECK_min': -0.1, 'SQUAT_DEPTH_CHECK_max': 1.0,
        },
        'source': "NSCA Guidelines (Parallel Squat Depth), NASM OHSA (LPHC neutral, avoid excessive forward lean)"
    },
    ('bench press', 'incline bench press', 'decline bench press'): {
        'metrics': ['ELBOW_ANGLE', 'ELBOW_FLARE', 'WRIST_ELBOW_STACK'],
        'thresholds': {
            'ELBOW_ANGLE_min': 85.0, 'ELBOW_ANGLE_max': 165.0,
            'ELBOW_FLARE_min': 30.0, 'ELBOW_FLARE_max': 75.0,  # NSCA: avoid extreme elbow flare; min relaxed to 30° to accommodate natural pressing angle
            'WRIST_ELBOW_STACK_min': 0.0, 'WRIST_ELBOW_STACK_max': 0.15,
        },
        'source': "NSCA Exercise Technique Manual: Five-point contact, rigid wrists above elbows, avoid extreme flare."
    },
    ('deadlift',): {
        'metrics': ['HIP_EXTENSION', 'KNEE_ANGLE', 'HIP_SHOULDER_HEIGHT', 'HIP_KNEE_HEIGHT_DEADLIFT', 'NECK_ALIGNMENT'],
        'thresholds': {
            'HIP_EXTENSION_min': 50.0, 'HIP_EXTENSION_max': 170.0,
            'KNEE_ANGLE_min': 85.0, 'KNEE_ANGLE_max': 175.0,  # NSCA: near-straight knees at lockout; raised to 175° to allow full lockout
            'HIP_SHOULDER_HEIGHT_min': 0.05, 'HIP_SHOULDER_HEIGHT_max': 1.0,  # NSCA: hips below shoulders; min relaxed to avoid false "too high" at lockout
            'HIP_KNEE_HEIGHT_DEADLIFT_min': -1.0, 'HIP_KNEE_HEIGHT_DEADLIFT_max': 0.05,  # NSCA: hips above knees at start; max raised slightly to avoid lockout collisions
            'NECK_ALIGNMENT_min': 0.0, 'NECK_ALIGNMENT_max': 0.3,  # NSCA: neutral cervical spine
        },
        'source': "NSCA Guidelines: Flat back/neutral spine, hips above knees and below shoulders."
    },
    ('romanian deadlift',): {
        'metrics': ['HIP_EXTENSION', 'SOFT_KNEES', 'NECK_ALIGNMENT'],
        'thresholds': {
            'HIP_EXTENSION_min': 50.0, 'HIP_EXTENSION_max': 170.0,
            'SOFT_KNEES_min': 120.0, 'SOFT_KNEES_max': 170.0,  # NSCA: slightly bent 'soft' knees
            'NECK_ALIGNMENT_min': 0.0, 'NECK_ALIGNMENT_max': 0.3,  # NSCA: neutral cervical spine
        },
        'source': "NSCA Guidelines: Hinge at hips with slightly bent 'soft' knees, neutral cervical spine."       
    },
    ('push-up',): {
        'metrics': ['ELBOW_ANGLE', 'ELBOW_FLARE', 'BODY_LINE'],
        'thresholds': {
            'ELBOW_ANGLE_min': 90.0, 'ELBOW_ANGLE_max': 170.0,
            'ELBOW_FLARE_min': 30.0, 'ELBOW_FLARE_max': 60.0,
            'BODY_LINE_min': 0.0, 'BODY_LINE_max': 0.15,
        },
        'source': "NASM / NSCA: Maintain neutral spine LPHC (plank position), tuck elbows slightly."
    },
    ('pull up',): {
        'metrics': ['ELBOW_ANGLE', 'BODY_SWING', 'CHIN_BAR_HEIGHT'],
        'thresholds': {
            'ELBOW_ANGLE_min': 50.0, 'ELBOW_ANGLE_max': 165.0,
            'BODY_SWING_min': 0.0, 'BODY_SWING_max': 80.0,  # NSCA: catches only gross swinging; suspended body + off-axis camera makes projected lean angle regularly exceed 50°
            'CHIN_BAR_HEIGHT_min': -0.4, 'CHIN_BAR_HEIGHT_max': 0.5,  # NSCA: chin must clear bar height; nose above bar as proxy
        },
        'source': "NSCA: Dead hang to chin over bar, minimal lower body swing."
    },
    ('plank',): {
        'metrics': ['BODY_LINE'],
        'thresholds': {
            'BODY_LINE_min': 0.0, 'BODY_LINE_max': 0.35,
        },
        'source': "NASM: LPHC neutral. Avoid lumbar extension (sagging) or hip flexion (piking)."
    },
    ('chest fly machine',): {
        'metrics': ['ELBOW_BEND', 'SHOULDER_ABDUCTION'],
        'thresholds': {
            'ELBOW_BEND_min': 110.0, 'ELBOW_BEND_max': 160.0,  # NSCA: maintain a slight, consistent elbow bend; do not lock out
            'SHOULDER_ABDUCTION_min': 50.0, 'SHOULDER_ABDUCTION_max': 85.0,  # NSCA: arms open to near-horizontal, not beyond 90°
        },
        'source': "NSCA: Maintain slight bend in elbows throughout fly motion."
    },
    ('hip thrust',): {
        'metrics': ['HIP_EXTENSION'],
        'thresholds': {
            'HIP_EXTENSION_min': 100.0, 'HIP_EXTENSION_max': 175.0,  # NSCA: full hip extension
        },
        'source': "NSCA: Full hip extension, vertical shins at terminal extension."
    },
    ('lat pulldown',): {
        'metrics': ['ELBOW_ANGLE', 'TORSO_SWING'],
        'thresholds': {
            'ELBOW_ANGLE_min': 60.0, 'ELBOW_ANGLE_max': 165.0,
            'TORSO_SWING_min': 0.0, 'TORSO_SWING_max': 80.0,  # NSCA: catches only gross rocking; off-axis camera regularly produces projected lean >50° even with correct technique
        },
        'source': "NSCA Guidelines: Slight torso lean back, pull bar to upper chest."
    },
    ('lateral raise',): {
        'metrics': ['SHOULDER_ABDUCTION', 'ELBOW_BEND', 'IMPINGEMENT_RISK', 'WRIST_ELBOW_HEIGHT'],
        'thresholds': {
            'SHOULDER_ABDUCTION_min': 20.0, 'SHOULDER_ABDUCTION_max': 90.0,
            'ELBOW_BEND_min': 130.0, 'ELBOW_BEND_max': 170.0,
            'IMPINGEMENT_RISK_min': 0.0, 'IMPINGEMENT_RISK_max': 0.5,
            'WRIST_ELBOW_HEIGHT_min': -0.1, 'WRIST_ELBOW_HEIGHT_max': 0.3,
        },
        'source': "NSCA: Abduct to 90 degrees max, slight elbow bend, lead with elbows to prevent impingement."
    },
    ('leg extension',): {
        'metrics': ['KNEE_ANGLE', 'TORSO_STABILITY'],
        'thresholds': {
            'KNEE_ANGLE_min': 80.0, 'KNEE_ANGLE_max': 175.0,  # NSCA: terminal knee extension
            'TORSO_STABILITY_min': 70.0, 'TORSO_STABILITY_max': 160.0,  # hip-shoulder-knee; very wide range since seat recline angle varies greatly between machines
        },
        'source': "NSCA: Controlled terminal knee extension, avoid explosive lockout."
    },
    ('leg raises',): {
        'metrics': ['HIP_EXTENSION', 'LEG_STRAIGHTNESS'],
        'thresholds': {
            'HIP_EXTENSION_min': 70.0, 'HIP_EXTENSION_max': 170.0,
            'LEG_STRAIGHTNESS_min': 120.0, 'LEG_STRAIGHTNESS_max': 180.0,  # NASM: maintain straight legs; max raised to 180° since hard_max=175° already prevents true hyperextension
        },
        'source': "NASM: LPHC stability. Maintain straight legs without lumbar spine compensation."
    },
    ('russian twist',): {
        'metrics': ['HIP_EXTENSION', 'TORSO_LEAN'],
        'thresholds': {
            'HIP_EXTENSION_min': 50.0, 'HIP_EXTENSION_max': 160.0,  # NSCA: v-sit posture; max raised — hip angle appears large when viewed from the side due to floor contact
            'TORSO_LEAN_min': 5.0, 'TORSO_LEAN_max': 80.0,  # NSCA: only catches near-lying-flat; off-axis camera means projected lean regularly exceeds 50° for normal v-sit posture
        },
        'source': "NSCA Core Training: Maintain v-sit posture, rotate from thoracic spine."
    },
    ('lunge',): {
        'metrics': ['KNEE_ANGLE', 'SHIN_ANGLE', 'BACK_ANGLE_VERTICAL'],
        'thresholds': {
            'KNEE_ANGLE_min': 30.0, 'KNEE_ANGLE_max': 175.0, 
            'SHIN_ANGLE_min': 0.0, 'SHIN_ANGLE_max': 45.0,  
            'BACK_ANGLE_VERTICAL_min': 0.0, 'BACK_ANGLE_VERTICAL_max': 75.0, 
        },
        'source': "NASM: Lunge kinematics. Knee should not significantly track past toes, torso upright."
    },
    ('shoulder press',): {
        'metrics': ['ELBOW_ANGLE', 'TORSO_ARCH', 'WRIST_ELBOW_STACK'],
        'thresholds': {
            'ELBOW_ANGLE_min': 50.0, 'ELBOW_ANGLE_max': 170.0,
            'TORSO_ARCH_min': 0.0, 'TORSO_ARCH_max': 80.0,  # NASM: catches only extreme arching; off-axis camera regularly produces projected lean >50° even with neutral posture
            'WRIST_ELBOW_STACK_min': 0.0, 'WRIST_ELBOW_STACK_max': 0.15,
        },
        'source': "NASM OHSA / NSCA: LPHC neutral, avoid excessive lumbar arch, wrists stacked over elbows."
    },
    ('t bar row',): {
        'metrics': ['ELBOW_ANGLE', 'BACK_ANGLE_HORIZONTAL', 'SOFT_KNEES', 'NECK_ALIGNMENT'],
        'thresholds': {
            'ELBOW_ANGLE_min': 70.0, 'ELBOW_ANGLE_max': 170.0,
            'BACK_ANGLE_HORIZONTAL_min': 20.0, 'BACK_ANGLE_HORIZONTAL_max': 60.0,  # NSCA: hinge posture, torso angled 20–60° from horizontal
            'SOFT_KNEES_min': 120.0, 'SOFT_KNEES_max': 178.0,  # NSCA: soft knees; raised to 178° — near full knee extension at top of row is biomechanically normal
            'NECK_ALIGNMENT_min': 0.0, 'NECK_ALIGNMENT_max': 0.3,  # NSCA: neutral cervical spine
        },
        'source': "NSCA: Hinge posture, neutral spine & neck, soft knees."
    },
    ('tricep dips',): {
        'metrics': ['ELBOW_ANGLE', 'TORSO_LEAN', 'SHOULDER_ELBOW_DEPTH'],
        'thresholds': {
            'ELBOW_ANGLE_min': 80.0, 'ELBOW_ANGLE_max': 170.0,
            'TORSO_LEAN_min': 0.0, 'TORSO_LEAN_max': 80.0,  # NSCA: catches only extreme forward hunch; off-axis camera regularly projects lean >50° with correct posture
            'SHOULDER_ELBOW_DEPTH_min': -1.0, 'SHOULDER_ELBOW_DEPTH_max': 0.2,  # NSCA: shoulders at/above elbow level; 0.2 absorbs depth estimation noise
        },
        'source': "NSCA: Descend until shoulders are parallel with elbows."
    },
    ('tricep pushdown',): {
        'metrics': ['ELBOW_ANGLE', 'ELBOW_PIN', 'TORSO_SWING'],
        'thresholds': {
            'ELBOW_ANGLE_min': 50.0, 'ELBOW_ANGLE_max': 170.0,
            'ELBOW_PIN_min': 0.0, 'ELBOW_PIN_max': 0.15,  # NSCA: upper arms stationary and pinned against sides
            'TORSO_SWING_min': 0.0, 'TORSO_SWING_max': 80.0,  # NSCA: catches only gross rocking; camera-projected trunk lean exceeds 50° with normal technique when filmed off-axis
        },
        'source': "NSCA: Upper arms stationary against sides, isolate elbow extension."
    }
}

# Flatten into map
EXERCISE_TO_CONFIG = {ex: conf for exercises, conf in _EXERCISE_GROUPS.items() for ex in exercises}
