// lib/services/pose_service.dart
import 'dart:typed_data';
import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'dio_helper.dart';

/// Service for interacting with the Pose Analysis endpoints.
///
/// Uses the same local backend as [RecommendationService] instead of the
/// ngrok-hosted [DioHelper.baseUrl].
class PoseService {
  // ── Backend base URL (same as RecommendationService) ──────────────────
  static const String _baseUrl = 'http://127.0.0.1:8000'; // Change in production

  // ── Dio instance for the local backend ────────────────────────────────
  static final Dio _dio = Dio(BaseOptions(
    baseUrl: _baseUrl,
    connectTimeout: const Duration(seconds: 30),
    sendTimeout: const Duration(seconds: 120),
    receiveTimeout: const Duration(seconds: 120),
  ));

  // ── Endpoint paths ────────────────────────────────────────────────────
  static String _analyzePath(String sessionId) =>
      '/pose/analyze/$sessionId';

  static String _historyPath(String sessionId) =>
      '/pose/history/$sessionId';

  static const String _exercisesPath = '/pose/exercises';

  // ── Public API ────────────────────────────────────────────────────────

  /// Upload a video file for pose analysis.
  ///
  /// On **mobile/desktop**, pass [videoFilePath].
  /// On **web**, pass [videoBytes] and [videoFileName].
  /// Returns the analysis result map.
  static Future<Map<String, dynamic>> analyzeVideo({
    required String sessionId,
    required String exerciseName,
    String? videoFilePath,
    Uint8List? videoBytes,
    String? videoFileName,
  }) async {
    assert(
      videoFilePath != null || (videoBytes != null && videoFileName != null),
      'Provide either videoFilePath (mobile) or videoBytes+videoFileName (web)',
    );

    late final MultipartFile videoFile;
    if (kIsWeb) {
      // Web: use in-memory bytes (file system paths don't exist)
      videoFile = MultipartFile.fromBytes(
        videoBytes!,
        filename: videoFileName ?? 'upload.mp4',
      );
    } else {
      // Mobile / Desktop: use file path
      videoFile = await MultipartFile.fromFile(
        videoFilePath!,
        filename: videoFilePath.split('/').last,
      );
    }

    final formData = FormData.fromMap({
      'exercise_name': exerciseName,
      'video': videoFile,
    });

    final response = await _dio.post(
      _analyzePath(sessionId),
      data: formData,
      options: Options(contentType: 'multipart/form-data'),
    );

    return Map<String, dynamic>.from(response.data as Map);
  }

  /// Get all past pose analysis results for a session.
  static Future<List<dynamic>> getHistory(String sessionId) async {
    final response = await _dio.get(_historyPath(sessionId));
    return List<dynamic>.from(response.data as List);
  }

  /// Get the list of supported exercise names.
  static Future<List<String>> getSupportedExercises() async {
    final response = await _dio.get(_exercisesPath);
    return List<String>.from(response.data as List);
  }

  /// Build the full download URL for a correction video.
  ///
  /// [relativePath] is the `video_url` returned by [analyzeVideo],
  /// e.g. `/pose-outputs/abc123.mp4`.
  static String correctionVideoUrl(String relativePath) {
    return '$_baseUrl$relativePath';
  }
}
