LEVEL_ORDER = {
    "Beginner": 0,
    "Intermediate": 1,
    "Expert": 2
}

GOAL_TYPE_WEIGHTS = {
    "fat_loss": {
        "Cardio": 3.0,
        "Strength": 2.0,
        "Plyometrics": 2.5,
        "Stretching": 1.0
    },
    "muscle_gain": {
        "Strength": 3.0,
        "Powerlifting": 3.0,
        "Olympic Weightlifting": 2.5,
        "Cardio": 0.5
    },
    "maintenance": {
        "Strength": 2.0,
        "Cardio": 2.0,
        "Stretching": 1.5
    },
    "endurance": {
        "Cardio": 3.0,
        "Plyometrics": 2.0,
        "Strength": 1.5
    }

}
FEEDBACK_WEIGHT = 0.3

def hard_filter_workouts(workouts, user):
    filtered = []

    for w in workouts:
        # Equipment check
        if w.equipment not in user.available_equipment and w.equipment != "Body Only":
            continue

        # Level check
        if LEVEL_ORDER[w.level] > LEVEL_ORDER[user.fitness_level.capitalize()]:
            continue

        filtered.append(w)

     

    return filtered

def score_workout(workout, user):
    score = 0.0

    # 1. Goal-based score
    goal_weights = GOAL_TYPE_WEIGHTS.get(user.goal_type, {})
    score += goal_weights.get(workout.workout_type, 0.5)

    # 2. Feedback-based adjustment
    feedback_pref = user.workout_type_preferences.get(
        workout.workout_type, 0
    )
    score += FEEDBACK_WEIGHT * feedback_pref

    # 3. Rating bonus
    if workout.rating is not None:
        score += 0.2 * workout.rating

    return score


def recommend_workouts(workouts, user, top_k=5):
    # 1. Hard filter
    valid_workouts = hard_filter_workouts(workouts, user)

    # 2. Score
    scored = [
        (w, score_workout(w, user))
        for w in valid_workouts
    ]

    # 3. Sort
    scored.sort(key=lambda x: x[1], reverse=True)

    # 4. Return top K workouts
    return [w for w, _ in scored[:top_k]]
