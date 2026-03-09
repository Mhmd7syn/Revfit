# Format: { 'names': [...], 'type': 'angle'|'horizontal_distance'|'vertical_distance'|'distance_from_line', 'joints': [...] }
_JOINT_GROUPS = {
    # --- ANGLES ---
    ('ELBOW_ANGLE', 'ELBOW_BEND', 'ARM_BEND'): {
        'type': 'angle',
        'joints': ['shoulder', 'elbow', 'wrist'],
        'message_high': 'Elbows too straight.',
        'message_low': 'Elbows bent too much.',
        'hard_max': 175.0
    },
    ('WRIST_ANGLE',): {
        'type': 'angle',
        'joints': ['elbow', 'wrist', 'index'],
        'message_low': 'Keep wrists straight. Do not curl or extend them.',
        'tolerance': 15.0
    },
    ('KNEE_ANGLE', 'LEG_STRAIGHTNESS', 'SOFT_KNEES'): {
        'type': 'angle',
        'joints': ['hip', 'knee', 'ankle'],
        'message_high': 'Legs too straight (Lockout?).',
        'message_low': 'Bend knees less.',
        'hard_max': 175.0
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
        'tolerance': 10.0  # Mercadal-Baudart et al. (2024): ±10° is acceptable for general fitness assessment
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
        'tolerance': 10.0  # Mercadal-Baudart et al. (2024): ±10° is standard for general fitness form checking
    },
    ('BACK_ANGLE_VERTICAL',): {
        'type': 'angle',
        'joints': ['vertical', 'hip', 'shoulder'],
        'message_high': 'Excessive forward lean.',
        'message_low': 'Torso too upright.',
        'tolerance': 10.0  # Mercadal-Baudart et al. (2024): ±10° is standard for general fitness form checking
    },
    ('BACK_ANGLE_HORIZONTAL',): {
        'type': 'angle',
        'joints': ['horizontal', 'hip', 'shoulder'],
        'message_high': 'Torso too upright.',
        'message_low': 'Torso too low.',
        'tolerance': 15.0  # Wider buffer needed; 2D camera cannot reliably measure horizontal plane angles
    },


    # --- HORIZONTAL DISTANCES ---
    ('SHOULDER_SWING', 'ELBOW_PIN', 'ELBOW_STABILITY'): {
        'type': 'horizontal_distance',
        'joints': ['shoulder', 'elbow'],
        'message_high': 'Keep elbows pinned to your sides (Horizontal Drift)!',
        'tolerance': 0.05  # 5% of torso length; accounts for natural arm sway and MediaPipe jitter
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
        'message_high': 'Keep neck neutral with spine.',
        'tolerance': 0.15  # Nose landmark is imprecise (Sim et al., 2024); allows ~15% torso-length deviation
    },
    ('HIP_ALIGNMENT',): {
        'type': 'distance_from_line',
        'joints': ['hip', 'shoulder', 'ankle'],
        'message_high': 'Align hips with body.'
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
            'ELBOW_PIN_min': 0.0, 'ELBOW_PIN_max': 0.20,  # NASM: elbows stay within ~20% torso-width of sides (loosened from 0.15)
            'TORSO_SWING_min': 0.0, 'TORSO_SWING_max': 20.0,  # NASM: minimal torso swing; loosened to 20° to reduce false positives
            'ELBOW_FLARE_min': 0.0, 'ELBOW_FLARE_max': 45.0,  # NASM: elbow angle from torso should stay <45°
            'WRIST_ANGLE_min': 105.0, 'WRIST_ANGLE_max': 180.0,  # NASM: neutral wrist; avoid full flexion
        },
        'source': "NASM Compensations: Avoid torso swing and elbow flare. Keep wrists neutral."
    },
    ('squat',): {
        'metrics': ['KNEE_ANGLE', 'HIP_EXTENSION', 'BACK_ANGLE_VERTICAL', 'SQUAT_DEPTH_CHECK'],
        'thresholds': {
            'KNEE_ANGLE_min': 60.0, 'KNEE_ANGLE_max': 170.0,
            'HIP_EXTENSION_min': 60.0, 'HIP_EXTENSION_max': 170.0,
            'BACK_ANGLE_VERTICAL_min': 10.0, 'BACK_ANGLE_VERTICAL_max': 45.0,
            'SQUAT_DEPTH_CHECK_min': -0.1, 'SQUAT_DEPTH_CHECK_max': 1.0,
        },
        'source': "NSCA Guidelines (Parallel Squat Depth), NASM OHSA (LPHC neutral, avoid excessive forward lean)"
    },
    ('bench press', 'incline bench press', 'decline bench press'): {
        'metrics': ['ELBOW_ANGLE', 'ELBOW_FLARE', 'WRIST_ELBOW_STACK'],
        'thresholds': {
            'ELBOW_ANGLE_min': 85.0, 'ELBOW_ANGLE_max': 165.0,
            'ELBOW_FLARE_min': 45.0, 'ELBOW_FLARE_max': 90.0,  # Loosened from 75°; incline press allows wider flare
            'WRIST_ELBOW_STACK_min': 0.0, 'WRIST_ELBOW_STACK_max': 0.15,
        },
        'source': "NSCA Exercise Technique Manual: Five-point contact, rigid wrists above elbows, avoid extreme flare."
    },
    ('deadlift',): {
        'metrics': ['HIP_EXTENSION', 'KNEE_ANGLE', 'HIP_SHOULDER_HEIGHT', 'HIP_KNEE_HEIGHT_DEADLIFT', 'NECK_ALIGNMENT'],
        'thresholds': {
            'HIP_EXTENSION_min': 50.0, 'HIP_EXTENSION_max': 170.0,
            'KNEE_ANGLE_min': 85.0, 'KNEE_ANGLE_max': 170.0,  # Loosened max from 165° to allow near-straight knees at lockout
            'HIP_SHOULDER_HEIGHT_min': 0.2, 'HIP_SHOULDER_HEIGHT_max': 1.0,
            'HIP_KNEE_HEIGHT_DEADLIFT_min': -1.0, 'HIP_KNEE_HEIGHT_DEADLIFT_max': -0.2,  # Loosened; too many false positives
            'NECK_ALIGNMENT_min': 0.0, 'NECK_ALIGNMENT_max': 0.5,  # Loosened from 0.3; 2D nose landmark imprecision causes excess flags
        },
        'source': "NSCA Guidelines: Flat back/neutral spine, hips above knees and below shoulders."
    },
    ('romanian deadlift',): {
        'metrics': ['HIP_EXTENSION', 'SOFT_KNEES', 'NECK_ALIGNMENT'],
        'thresholds': {
            'HIP_EXTENSION_min': 50.0, 'HIP_EXTENSION_max': 170.0,
            'SOFT_KNEES_min': 120.0, 'SOFT_KNEES_max': 175.0,  # Loosened; 'Bend knees less' fires too often
            'NECK_ALIGNMENT_min': 0.0, 'NECK_ALIGNMENT_max': 0.5,  # Loosened from 0.3; 2D nose landmark imprecision causes excess flags
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
            'BODY_SWING_min': 0.0, 'BODY_SWING_max': 15.0,  # NSCA: minimal lower body swing; <15° considered controlled
            'CHIN_BAR_HEIGHT_min': -0.4, 'CHIN_BAR_HEIGHT_max': 0.5,  # NSCA: chin must clear bar height; nose above bar as proxy
        },
        'source': "NSCA: Dead hang to chin over bar, minimal lower body swing."
    },
    ('plank',): {
        'metrics': ['BODY_LINE'],
        'thresholds': {
            'BODY_LINE_min': 0.0, 'BODY_LINE_max': 0.15,
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
        'metrics': ['HIP_EXTENSION', 'SHIN_ANGLE'],
        'thresholds': {
            'HIP_EXTENSION_min': 90.0, 'HIP_EXTENSION_max': 175.0,  # Loosened min from 100°
            'SHIN_ANGLE_min': 0.0, 'SHIN_ANGLE_max': 35.0,  # Loosened from 15°; shins rarely perfectly vertical in practice
        },
        'source': "NSCA: Full hip extension, vertical shins at terminal extension."
    },
    ('lat pulldown',): {
        'metrics': ['ELBOW_ANGLE', 'TORSO_SWING'],
        'thresholds': {
            'ELBOW_ANGLE_min': 60.0, 'ELBOW_ANGLE_max': 165.0,
            'TORSO_SWING_min': 0.0, 'TORSO_SWING_max': 20.0,
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
            'KNEE_ANGLE_min': 80.0, 'KNEE_ANGLE_max': 170.0,
            'TORSO_STABILITY_min': 90.0, 'TORSO_STABILITY_max': 130.0,
        },
        'source': "NSCA: Controlled terminal knee extension, avoid explosive lockout."
    },
    ('leg raises',): {
        'metrics': ['HIP_EXTENSION', 'LEG_STRAIGHTNESS'],
        'thresholds': {
            'HIP_EXTENSION_min': 70.0, 'HIP_EXTENSION_max': 170.0,
            'LEG_STRAIGHTNESS_min': 120.0, 'LEG_STRAIGHTNESS_max': 175.0,
        },
        'source': "NASM: LPHC stability. Maintain straight legs without lumbar spine compensation."
    },
    ('russian twist',): {
        'metrics': ['HIP_EXTENSION', 'TORSO_LEAN'],
        'thresholds': {
            'HIP_EXTENSION_min': 50.0, 'HIP_EXTENSION_max': 120.0,
            'TORSO_LEAN_min': 20.0, 'TORSO_LEAN_max': 60.0,
        },
        'source': "NSCA Core Training: Maintain v-sit posture, rotate from thoracic spine."
    },
    ('shoulder press',): {
        'metrics': ['ELBOW_ANGLE', 'TORSO_ARCH', 'WRIST_ELBOW_STACK'],
        'thresholds': {
            'ELBOW_ANGLE_min': 50.0, 'ELBOW_ANGLE_max': 170.0,
            'TORSO_ARCH_min': 0.0, 'TORSO_ARCH_max': 25.0,
            'WRIST_ELBOW_STACK_min': 0.0, 'WRIST_ELBOW_STACK_max': 0.15,
        },
        'source': "NASM OHSA / NSCA: LPHC neutral, avoid excessive lumbar arch, wrists stacked over elbows."
    },
    ('t bar row',): {
        'metrics': ['ELBOW_ANGLE', 'BACK_ANGLE_HORIZONTAL', 'SOFT_KNEES', 'NECK_ALIGNMENT'],
        'thresholds': {
            'ELBOW_ANGLE_min': 70.0, 'ELBOW_ANGLE_max': 170.0,
            'BACK_ANGLE_HORIZONTAL_min': 10.0, 'BACK_ANGLE_HORIZONTAL_max': 75.0,  # Loosened from 20-60°; 2D camera makes horizontal angle unreliable
            'SOFT_KNEES_min': 120.0, 'SOFT_KNEES_max': 175.0,  # Loosened; 'Bend knees less' fires too often
            'NECK_ALIGNMENT_min': 0.0, 'NECK_ALIGNMENT_max': 0.5,  # Loosened from 0.3; nose landmark imprecision in hinge posture
        },
        'source': "NSCA: Hinge posture, neutral spine & neck, soft knees."
    },
    ('tricep dips',): {
        'metrics': ['ELBOW_ANGLE', 'TORSO_LEAN', 'SHOULDER_ELBOW_DEPTH'],
        'thresholds': {
            'ELBOW_ANGLE_min': 80.0, 'ELBOW_ANGLE_max': 170.0,
            'TORSO_LEAN_min': 0.0, 'TORSO_LEAN_max': 30.0,
            'SHOULDER_ELBOW_DEPTH_min': -1.0, 'SHOULDER_ELBOW_DEPTH_max': 0.1,
        },
        'source': "NSCA: Descend until shoulders are parallel with elbows."
    },
    ('tricep pushdown',): {
        'metrics': ['ELBOW_ANGLE', 'ELBOW_PIN', 'TORSO_SWING'],
        'thresholds': {
            'ELBOW_ANGLE_min': 50.0, 'ELBOW_ANGLE_max': 170.0,
            'ELBOW_PIN_min': 0.0, 'ELBOW_PIN_max': 0.15,  # NSCA: upper arms stationary and pinned against sides
            'TORSO_SWING_min': 0.0, 'TORSO_SWING_max': 15.0,  # NSCA: avoid torso rocking; <15° is acceptable
        },
        'source': "NSCA: Upper arms stationary against sides, isolate elbow extension."
    }
}

# Flatten into map
EXERCISE_TO_CONFIG = {ex: conf for exercises, conf in _EXERCISE_GROUPS.items() for ex in exercises}
