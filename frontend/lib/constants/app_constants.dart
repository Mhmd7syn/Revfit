// lib/constants/app_constants.dart
class AppConstants {
  // Map countries to cuisine types (must match backend)
  static const Map<String, String> locationToCuisine = {
    'Egypt': 'middle eastern',
    'Italy': 'italian',
    'Japan': 'japanese',
    'Mexico': 'mexican',
    'India': 'indian',
    'France': 'french',
    'China': 'chinese',
    'USA': 'american',
    'Greece': 'mediterranean',
    'Spain': 'spanish',
    'Thailand': 'thai',
    // Add more as needed
  };

  // Diet types (for dropdown)
  static const List<String> dietTypes = [
    'omnivore',
    'vegetarian',
    'vegan',
    'ketogenic',
    'paleo',
    'mediterranean',
    'gluten free',
  ];

  // Protein focus levels
  static const List<String> proteinFocusLevels = ['low', 'medium', 'high'];

  // Cooking time preferences
  static const List<String> cookingTimePreferences = ['quick', 'flexible'];

  // Meal counts
  static const List<int> mealCounts = [3, 4, 5, 6];
}
