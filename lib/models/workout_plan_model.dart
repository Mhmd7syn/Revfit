// lib/models/workout_plan_model.dart

class WorkoutPlanModel {
  final String planName;
  final int daysPerWeek;
  final String fitnessLevel;
  final List<WorkoutDay> schedule;
  final List<String>? notes;

  WorkoutPlanModel({
    required this.planName,
    required this.daysPerWeek,
    required this.fitnessLevel,
    required this.schedule,
    this.notes,
  });

  factory WorkoutPlanModel.fromMap(Map<String, dynamic> map) {
    return WorkoutPlanModel(
      planName: map['plan_name'] ?? map['planName'] ?? 'Workout Plan',
      daysPerWeek: (map['days_per_week'] ?? map['daysPerWeek'] ?? 0) as int,
      fitnessLevel: map['fitness_level'] ?? map['fitnessLevel'] ?? '',
      schedule: (map['schedule'] as List<dynamic>? ?? [])
          .map((d) => WorkoutDay.fromMap(d as Map<String, dynamic>))
          .toList(),
      notes: (map['notes'] as List<dynamic>?)?.cast<String>(),
    );
  }
}

class WorkoutDay {
  final int day;
  final String dayName;
  final bool isRestDay;
  final String? focus;
  final List<ExerciseItem> exercises;

  WorkoutDay({
    required this.day,
    required this.dayName,
    required this.isRestDay,
    this.focus,
    required this.exercises,
  });

  factory WorkoutDay.fromMap(Map<String, dynamic> map) {
    return WorkoutDay(
      day: (map['day'] ?? 1) as int,
      dayName: map['day_name'] ?? map['dayName'] ?? 'Day ${map['day'] ?? 1}',
      isRestDay: map['is_rest_day'] ?? map['isRestDay'] ?? false,
      focus: map['focus'] as String?,
      exercises: (map['exercises'] as List<dynamic>? ?? [])
          .map((e) => ExerciseItem.fromMap(e as Map<String, dynamic>))
          .toList(),
    );
  }
}

class ExerciseItem {
  final String name;
  final String? bodyPart;
  final String? equipment;
  final int? sets;
  final String? reps; // e.g. "8-12" or "15"
  final int? durationSeconds;
  final String? notes;
  final String? difficulty;

  ExerciseItem({
    required this.name,
    this.bodyPart,
    this.equipment,
    this.sets,
    this.reps,
    this.durationSeconds,
    this.notes,
    this.difficulty,
  });

  factory ExerciseItem.fromMap(Map<String, dynamic> map) {
    return ExerciseItem(
      name: map['name'] ?? map['exercise_name'] ?? '',
      bodyPart: map['body_part'] ?? map['bodyPart'] as String?,
      equipment: map['equipment'] as String?,
      sets: map['sets'] as int?,
      reps: map['reps']?.toString(),
      durationSeconds: map['duration_seconds'] as int?,
      notes: map['notes'] as String?,
      difficulty: map['difficulty'] as String?,
    );
  }

  String get setsRepsDisplay {
    if (sets != null && reps != null) return '${sets}x$reps';
    if (sets != null) return '${sets} sets';
    if (durationSeconds != null) return '${durationSeconds}s';
    return '';
  }
}
