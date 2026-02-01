from filters import recommend_workouts, score_workout
from workouts import WorkoutItem
from user_profile import UserProfile


# ---------------- Fake workouts ----------------
workouts = [
    WorkoutItem(
        workout_id="w1",
        name="Push Ups",
        workout_type="Strength",
        body_part="Chest",
        equipment="Body Only",
        level="Beginner",
        rating=4.5
    ),
    WorkoutItem(
        workout_id="w2",
        name="Jump Rope",
        workout_type="Cardio",
        body_part="Calves",
        equipment="Body Only",
        level="Beginner",
        rating=4.2
    ),
    WorkoutItem(
        workout_id="w3",
        name="Squats",
        workout_type="Strength",
        body_part="Quadriceps",
        equipment="Body Only",
        level="Beginner",
        rating=4.7
    ),
    WorkoutItem(
        workout_id="w4",
        name="Stretch Routine",
        workout_type="Stretching",
        body_part="Hamstrings",
        equipment="Body Only",
        level="Beginner",
        rating=None
    ),
    WorkoutItem(
        workout_id="w5",
        name="Bench Press",
        workout_type="Strength",
        body_part="Chest",
        equipment="Body Only",
        level="Beginner",
        rating=4.6
    ),
]


# ---------------- Fake user ----------------
user = UserProfile(
    age=23,
    height_cm=175,
    weight_kg=75,
    goal_type="muscle_gain",
    fitness_level="beginner",
    workout_location="home",
    available_equipment=["Body Only"]
)


# ---------------- BEFORE feedback ----------------
print("Recommendations BEFORE feedback:")
before = recommend_workouts(workouts, user, top_k=5)
for w in before:
    print(w.name, "-", w.workout_type)

print("\nWorkout scores before feedback:")
for w in workouts:
    print(w.name, "=>", round(score_workout(w, user), 2))


# ---------------- Feedback ----------------
# User REALLY dislikes Squats
user.add_workout_feedback(workouts[2], liked=False)
user.add_workout_feedback(workouts[2], liked=False)
user.add_workout_feedback(workouts[2], liked=False)

# User likes Push Ups
user.add_workout_feedback(workouts[0], liked=True)


# ---------------- AFTER feedback ----------------
print("\nRecommendations AFTER feedback:")
after = recommend_workouts(workouts, user, top_k=5)
for w in after:
    print(w.name, "-", w.workout_type)


# ---------------- Debug: show scores ----------------
print("\nWorkout scores AFTER feedback:")
for w in workouts:
    print(w.name, "=>", round(score_workout(w, user), 2))