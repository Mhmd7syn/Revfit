from filters import recommend_workouts
from workouts import WorkoutItem
from user_profile import UserProfile

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
        name="Burpees",
        workout_type="Plyometrics",
        body_part="Full Body",
        equipment="Body Only",
        level="Intermediate",
        rating=4.0
    ),
    WorkoutItem(
        workout_id="w5",
        name="Stretch Routine",
        workout_type="Stretching",
        body_part="Hamstrings",
        equipment="Body Only",
        level="Beginner",
        rating=None
    ),
]

user = UserProfile(
    age=23,
    height_cm=175,
    weight_kg=75,
    goal_type="muscle_gain",
    fitness_level="beginner",
    workout_location="home",
    available_equipment=["Body Only"]
)

if __name__ == "__main__":
    initial_recs = recommend_workouts(workouts, user, top_k=5)

    print("Recommendations BEFORE feedback:")
    for w in initial_recs:
        print(w.name, "-", w.workout_type)


    user.add_workout_feedback(workouts[0], liked=True)   # Push Ups
    user.add_workout_feedback(workouts[2], liked=True)   # Squats
    user.add_workout_feedback(workouts[1], liked=False)  # Jump Rope


    updated_recs = recommend_workouts(workouts, user, top_k=5)

    print("\nRecommendations AFTER feedback:")
    for w in updated_recs:
        print(w.name, "-", w.workout_type)
