// lib/models/user_model.dart
import 'package:cloud_firestore/cloud_firestore.dart';

class UserModel {
  final String uid;
  final String name;
  final String email;
  final String phone;
  final int age;
  final String gender;
  final double height;
  final double weight;
  final String goal;
  final bool isVegetarian;

  // ── Computed at signup & stored in Firestore ──────────────────────────────
  /// e.g. 'fat_loss' | 'muscle_gain' | 'endurance' | 'strength' | 'maintenance'
  final String goalType;

  /// Body-Mass-Index rounded to 1 decimal (null if height/weight not provided)
  final double? bmi;

  /// Default diet type derived from isVegetarian: 'vegetarian' | 'omnivore'
  final String defaultDietType;

  UserModel({
    required this.uid,
    required this.name,
    required this.email,
    required this.phone,
    required this.age,
    required this.gender,
    required this.height,
    required this.weight,
    required this.goal,
    required this.isVegetarian,
    // Computed fields – have sensible defaults so fromMap never crashes
    this.goalType = 'maintenance',
    this.bmi,
    this.defaultDietType = 'omnivore',
  });

  // ── Firestore serialisation ───────────────────────────────────────────────

  Map<String, dynamic> toMap() {
    return {
      'uid': uid,
      'name': name,
      'email': email,
      'phone': phone,
      'age': age,
      'gender': gender,
      'height': height,
      'weight': weight,
      'goal': goal,
      'isVegetarian': isVegetarian,
      // Computed fields
      'goalType': goalType,
      'bmi': bmi,
      'defaultDietType': defaultDietType,
    };
  }

  factory UserModel.fromMap(Map<String, dynamic> map) {
    return UserModel(
      uid: map['uid'] ?? '',
      name: map['name'] ?? '',
      email: map['email'] ?? '',
      phone: map['phone'] ?? '',
      age: (map['age'] ?? 0) as int,
      gender: map['gender'] ?? '',
      height: (map['height'] ?? 0).toDouble(),
      weight: map['weight'] != null ? (map['weight'] as num).toDouble() : 0.0,
      goal: map['goal'] ?? '',
      isVegetarian: map['isVegetarian'] ?? false,
      // Computed fields
      goalType: map['goalType'] ?? 'maintenance',
      bmi: map['bmi'] != null ? (map['bmi'] as num).toDouble() : null,
      defaultDietType: map['defaultDietType'] ?? 'omnivore',
    );
  }

  /// Returns a copy with updated fields (useful for profile editing)
  UserModel copyWith({
    String? name,
    String? phone,
    int? age,
    String? gender,
    double? height,
    double? weight,
    String? goal,
    bool? isVegetarian,
    String? goalType,
    double? bmi,
    String? defaultDietType,
  }) {
    return UserModel(
      uid: uid,
      name: name ?? this.name,
      email: email,
      phone: phone ?? this.phone,
      age: age ?? this.age,
      gender: gender ?? this.gender,
      height: height ?? this.height,
      weight: weight ?? this.weight,
      goal: goal ?? this.goal,
      isVegetarian: isVegetarian ?? this.isVegetarian,
      goalType: goalType ?? this.goalType,
      bmi: bmi ?? this.bmi,
      defaultDietType: defaultDietType ?? this.defaultDietType,
    );
  }
}
