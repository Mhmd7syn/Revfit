// lib/models/diet_plan_model.dart

class DietPlanModel {
  final String planName;
  final int totalCalories;
  final MacroBreakdown macros;
  final List<DayPlan> days;
  final List<String>? notes;

  DietPlanModel({
    required this.planName,
    required this.totalCalories,
    required this.macros,
    required this.days,
    this.notes,
  });

  factory DietPlanModel.fromMap(Map<String, dynamic> map) {
    return DietPlanModel(
      planName: map['plan_name'] ?? map['planName'] ?? 'Diet Plan',
      totalCalories: (map['total_calories'] ?? map['totalCalories'] ?? 0) as int,
      macros: MacroBreakdown.fromMap(
        map['macros'] ?? map['macro_breakdown'] ?? {},
      ),
      days: (map['days'] as List<dynamic>? ?? [])
          .map((d) => DayPlan.fromMap(d as Map<String, dynamic>))
          .toList(),
      notes: (map['notes'] as List<dynamic>?)?.cast<String>(),
    );
  }
}

class MacroBreakdown {
  final double proteinG;
  final double carbsG;
  final double fatG;

  MacroBreakdown({
    required this.proteinG,
    required this.carbsG,
    required this.fatG,
  });

  factory MacroBreakdown.fromMap(Map<String, dynamic> map) {
    return MacroBreakdown(
      proteinG: (map['protein_g'] ?? map['protein'] ?? 0).toDouble(),
      carbsG: (map['carbs_g'] ?? map['carbs'] ?? 0).toDouble(),
      fatG: (map['fat_g'] ?? map['fat'] ?? 0).toDouble(),
    );
  }
}

class DayPlan {
  final int day;
  final String? dayName;
  final List<MealItem> meals;

  DayPlan({required this.day, this.dayName, required this.meals});

  factory DayPlan.fromMap(Map<String, dynamic> map) {
    return DayPlan(
      day: (map['day'] ?? 1) as int,
      dayName: map['day_name'] as String?,
      meals: (map['meals'] as List<dynamic>? ?? [])
          .map((m) => MealItem.fromMap(m as Map<String, dynamic>))
          .toList(),
    );
  }
}

class MealItem {
  final String mealType;
  final String name;
  final int calories;
  final double proteinG;
  final double carbsG;
  final double fatG;
  final String? recipe;
  final List<String>? ingredients;

  MealItem({
    required this.mealType,
    required this.name,
    required this.calories,
    required this.proteinG,
    required this.carbsG,
    required this.fatG,
    this.recipe,
    this.ingredients,
  });

  factory MealItem.fromMap(Map<String, dynamic> map) {
    return MealItem(
      mealType: map['meal_type'] ?? map['mealType'] ?? 'meal',
      name: map['name'] ?? '',
      calories: (map['calories'] ?? 0) as int,
      proteinG: (map['protein_g'] ?? map['protein'] ?? 0).toDouble(),
      carbsG: (map['carbs_g'] ?? map['carbs'] ?? 0).toDouble(),
      fatG: (map['fat_g'] ?? map['fat'] ?? 0).toDouble(),
      recipe: map['recipe'] as String?,
      ingredients: (map['ingredients'] as List<dynamic>?)?.cast<String>(),
    );
  }
}
