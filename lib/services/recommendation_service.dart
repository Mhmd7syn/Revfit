// lib/services/recommendation_service.dart
//
// Updated for Content-Based Filtering architecture (Experiment 3).
// Workout/meal recommend endpoints now use query parameters instead of
// JSON bodies. All user constraints come from the server-side session.

import 'dart:convert';
import 'package:dio/dio.dart';
import 'dio_helper.dart';

/// Thrown when the session_id is not found on the server (HTTP 404).
class SessionExpiredException implements Exception {
  final String sessionId;
  SessionExpiredException(this.sessionId);

  @override
  String toString() => 'Session "$sessionId" has expired or does not exist.';
}

/// Thrown when Spoonacular rate limit is exceeded (HTTP 429).
class RateLimitExceededException implements Exception {
  final String message;
  RateLimitExceededException(
      [this.message =
          'Spoonacular API rate limit exceeded. Please try again later.']);

  @override
  String toString() => message;
}

class RecommendationService {
  // ------------------------------------------------------------------ //
  //  API Endpoint Constants                                            //
  // ------------------------------------------------------------------ //

  static const String _baseUrl = 'http://127.0.0.1:8000'; // Change in production

  // Users
  static const String _createUser = '$_baseUrl/users/';
  static String _getUser(String sessionId) => '$_baseUrl/users/$sessionId';
  static String _updateGoal(String sessionId) => '$_baseUrl/users/$sessionId/goal';
  static String _getMacros(String sessionId) => '$_baseUrl/users/$sessionId/macros';

  // Workouts
  static String _recommendWorkouts(String sessionId) =>
      '$_baseUrl/workouts/recommend/$sessionId';
  static String _workoutPlan(String sessionId) =>
      '$_baseUrl/workouts/plan/$sessionId';
  static String _getWorkout(String workoutId) => '$_baseUrl/workouts/$workoutId';
  static String _filterWorkouts(String sessionId) =>
      '$_baseUrl/workouts/filter/$sessionId';
  static const String _listWorkouts = '$_baseUrl/workouts/';
  static const String _workoutMetadata = '$_baseUrl/workouts/meta';

  // Meals / Recipes
  static String _fetchMeals(String sessionId) => '$_baseUrl/meals/fetch/$sessionId';
  static String _recommendMeals(String sessionId) =>
      '$_baseUrl/meals/recommend/$sessionId';
  static String _getRecipe(String recipeId) => '$_baseUrl/meals/recipe/$recipeId';

  // Meal Plan
  static String _generateMealPlan(String sessionId) =>
      '$_baseUrl/meal-plan/generate/$sessionId';
  static String _slotTargets(String sessionId) =>
      '$_baseUrl/meal-plan/slot-targets/$sessionId';

  // Feedback
  static String _mealFeedback(String sessionId) => '$_baseUrl/feedback/meal/$sessionId';
  static String _workoutFeedback(String sessionId) =>
      '$_baseUrl/feedback/workout/$sessionId';
  static String _getFeedback(String sessionId) => '$_baseUrl/feedback/$sessionId';
  static String _resetFeedback(String sessionId) =>
      '$_baseUrl/feedback/$sessionId/reset';
  static const String _feedbackStoreSummary = '$_baseUrl/feedback/store/summary';

  // ------------------------------------------------------------------ //
  //  Session Management                                                //
  // ------------------------------------------------------------------ //

  /// Create a new user session. Returns the session_id.
  Future<String> createSession(Map<String, dynamic> userData) async {
    try {
      final response = await DioHelper.postData(
        path: _createUser,
        data: userData,
      );
      // Response contains {"session_id": "...", "target_calories": ...}
      return response.data['session_id'] as String;
    } catch (e) {
      throw Exception('Failed to create session: $e');
    }
  }

  /// Get user profile for a session.
  Future<Map<String, dynamic>> getUserProfile(String sessionId) async {
    try {
      final response = await DioHelper.getData(path: _getUser(sessionId));
      return response.data;
    } catch (e) {
      throw Exception('Failed to get user profile: $e');
    }
  }

  /// Update user's goal type (recalculates calories).
  Future<Map<String, dynamic>> updateGoal(String sessionId, String goalType) async {
    try {
      final response = await DioHelper.putData(
        path: _updateGoal(sessionId),
        data: {'goal_type': goalType},
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to update goal: $e');
    }
  }

  /// Get daily macro targets for a user.
  Future<Map<String, dynamic>> getMacros(String sessionId) async {
    try {
      final response = await DioHelper.getData(path: _getMacros(sessionId));
      return response.data;
    } catch (e) {
      throw Exception('Failed to get macros: $e');
    }
  }

  // ------------------------------------------------------------------ //
  //  Workout Recommendations                                           //
  // ------------------------------------------------------------------ //

  /// Get top-K personalised workout recommendations.
  ///
  /// Uses Content-Based Filtering — all user constraints are read from
  /// the server-side session. Only `top_k` is passed as a query param.
  Future<List<dynamic>> getWorkoutPlan(
    String sessionId, {
    int topK = 5,
  }) async {
    try {
      final response = await DioHelper.postData(
        path: '${_recommendWorkouts(sessionId)}?top_k=$topK',
        data: {},
      );
      // Response is a List of workout objects
      return response.data as List;
    } on DioException catch (e) {
      _handleApiError(e, sessionId);
      rethrow;
    } catch (e) {
      throw Exception('Failed to get workout recommendations: $e');
    }
  }

  /// Get a structured day-by-day workout plan (multiple exercises per day).
  Future<Map<String, dynamic>> getStructuredWorkoutPlan(
    String sessionId, {
    int topK = 5,
  }) async {
    try {
      final response = await DioHelper.postData(
        path: '${_workoutPlan(sessionId)}?top_k=$topK',
        data: {},
      );
      // Response is a WorkoutPlanResponse with days → exercises
      return response.data as Map<String, dynamic>;
    } on DioException catch (e) {
      _handleApiError(e, sessionId);
      rethrow;
    } catch (e) {
      throw Exception('Failed to get structured workout plan: $e');
    }
  }

  /// Get all workouts that pass the hard filters (no scoring).
  Future<List<dynamic>> filterWorkouts(String sessionId) async {
    try {
      final response = await DioHelper.getData(path: _filterWorkouts(sessionId));
      return response.data as List;
    } catch (e) {
      throw Exception('Failed to filter workouts: $e');
    }
  }

  /// Get a single workout by ID.
  Future<Map<String, dynamic>> getWorkout(String workoutId) async {
    try {
      final response = await DioHelper.getData(path: _getWorkout(workoutId));
      return response.data;
    } catch (e) {
      throw Exception('Failed to get workout: $e');
    }
  }

  /// List all workouts with optional filters.
  Future<Map<String, dynamic>> listWorkouts({
    String? workoutType,
    String? bodyPart,
    String? equipment,
    String? level,
    int limit = 50,
    int offset = 0,
  }) async {
    try {
      final queryParams = {
        if (workoutType != null) 'workout_type': workoutType,
        if (bodyPart != null) 'body_part': bodyPart,
        if (equipment != null) 'equipment': equipment,
        if (level != null) 'level': level,
        'limit': limit,
        'offset': offset,
      };
      final response = await DioHelper.getData(
        path: _listWorkouts,
        queryParameters: queryParams,
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to list workouts: $e');
    }
  }

  /// Get workout metadata (unique filter values).
  Future<Map<String, dynamic>> getWorkoutMetadata() async {
    try {
      final response = await DioHelper.getData(path: _workoutMetadata);
      return response.data;
    } catch (e) {
      throw Exception('Failed to get workout metadata: $e');
    }
  }

  // ------------------------------------------------------------------ //
  //  Meal / Recipe Recommendations                                     //
  // ------------------------------------------------------------------ //

  /// Fetch and filter meals (no scoring).
  ///
  /// Uses query parameters — no request body needed.
  Future<Map<String, dynamic>> fetchMeals(
    String sessionId, {
    int numFetch = 20,
  }) async {
    try {
      final response = await DioHelper.postData(
        path: '${_fetchMeals(sessionId)}?num_fetch=$numFetch',
        data: {},
      );
      return response.data;
    } on DioException catch (e) {
      _handleApiError(e, sessionId);
      rethrow;
    } catch (e) {
      throw Exception('Failed to fetch meals: $e');
    }
  }

  /// Get top-K personalised meal recommendations.
  ///
  /// Uses Content-Based Filtering — all user constraints are read from
  /// the server-side session. Parameters are passed as query params.
  Future<List<dynamic>> recommendMeals(
    String sessionId, {
    int topK = 5,
    int numFetch = 20,
  }) async {
    try {
      final response = await DioHelper.postData(
        path: '${_recommendMeals(sessionId)}?top_k=$topK&num_fetch=$numFetch',
        data: {},
      );
      return response.data as List;
    } on DioException catch (e) {
      _handleApiError(e, sessionId);
      rethrow;
    } catch (e) {
      throw Exception('Failed to recommend meals: $e');
    }
  }

  /// Get a single recipe by ID.
  Future<Map<String, dynamic>> getRecipe(String recipeId) async {
    try {
      final response = await DioHelper.getData(path: _getRecipe(recipeId));
      return response.data;
    } catch (e) {
      throw Exception('Failed to get recipe: $e');
    }
  }

  // ------------------------------------------------------------------ //
  //  Meal Plan Generation                                              //
  // ------------------------------------------------------------------ //

  /// Generate a full daily meal plan.
  ///
  /// Uses query parameters — no request body needed.
  Future<Map<String, dynamic>> generateMealPlan(
    String sessionId, {
    int topK = 5,
    int numFetch = 20,
  }) async {
    try {
      final response = await DioHelper.postData(
        path: '${_generateMealPlan(sessionId)}?top_k=$topK&num_fetch=$numFetch',
        data: {},
      );
      // Returns MealPlanResponse as JSON
      return response.data;
    } on DioException catch (e) {
      _handleApiError(e, sessionId);
      rethrow;
    } catch (e) {
      throw Exception('Failed to generate meal plan: $e');
    }
  }

  /// Get per-slot macro targets (no API call needed, just calculation).
  Future<Map<String, dynamic>> getSlotTargets(String sessionId) async {
    try {
      final response = await DioHelper.getData(path: _slotTargets(sessionId));
      return response.data;
    } catch (e) {
      throw Exception('Failed to get slot targets: $e');
    }
  }

  // ------------------------------------------------------------------ //
  //  Feedback                                                         //
  // ------------------------------------------------------------------ //

  /// Record meal like/dislike.
  Future<void> sendMealFeedback(
    String sessionId,
    String recipeId,
    bool liked,
  ) async {
    try {
      await DioHelper.postData(
        path: _mealFeedback(sessionId),
        data: {'recipe_id': recipeId, 'liked': liked},
      );
    } catch (e) {
      throw Exception('Failed to send meal feedback: $e');
    }
  }

  /// Record workout like/dislike.
  Future<void> sendWorkoutFeedback(
    String sessionId,
    String workoutId,
    bool liked,
  ) async {
    try {
      await DioHelper.postData(
        path: _workoutFeedback(sessionId),
        data: {'workout_id': workoutId, 'liked': liked},
      );
    } catch (e) {
      throw Exception('Failed to send workout feedback: $e');
    }
  }

  /// Get all feedback for a session.
  Future<Map<String, dynamic>> getFeedback(String sessionId) async {
    try {
      final response = await DioHelper.getData(path: _getFeedback(sessionId));
      return response.data;
    } catch (e) {
      throw Exception('Failed to get feedback: $e');
    }
  }

  /// Reset all feedback for a session.
  Future<void> resetFeedback(String sessionId) async {
    try {
      await DioHelper.deleteData(path: _resetFeedback(sessionId));
    } catch (e) {
      throw Exception('Failed to reset feedback: $e');
    }
  }

  /// Get global feedback store summary.
  Future<Map<String, dynamic>> getFeedbackStoreSummary() async {
    try {
      final response = await DioHelper.getData(path: _feedbackStoreSummary);
      return response.data;
    } catch (e) {
      throw Exception('Failed to get feedback store summary: $e');
    }
  }

  // ------------------------------------------------------------------ //
  //  Error Handling Helpers                                             //
  // ------------------------------------------------------------------ //

  /// Inspect a DioException for known API error patterns and throw
  /// domain-specific exceptions.
  static Never _handleApiError(DioException e, [String? sessionId]) {
    final statusCode = e.response?.statusCode;

    // Session not found
    if (statusCode == 404 && sessionId != null) {
      throw SessionExpiredException(sessionId);
    }

    // Spoonacular rate limit exceeded
    if (statusCode == 429) {
      final detail = e.response?.data is Map
          ? (e.response!.data['detail'] as String? ?? '')
          : '';
      throw RateLimitExceededException(
        detail.isNotEmpty
            ? detail
            : 'API rate limit exceeded. Please try again later.',
      );
    }

    // Re-throw for unhandled cases
    throw e;
  }
}