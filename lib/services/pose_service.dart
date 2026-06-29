// lib/services/pose_service.dart
import 'dart:typed_data';
import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:web_socket_channel/web_socket_channel.dart';
import 'dio_helper.dart';

/// Service for interacting with the Pose Analysis endpoints.
///
/// Uses the same local backend as [RecommendationService] instead of the
/// ngrok-hosted [DioHelper.baseUrl].
class PoseService {
  // ── Backend base URL (same as RecommendationService) ──────────────────
  static const String _baseUrl = 'http://192.168.1.27:8000'; // Change in production

  // ── WebSocket base URL ────────────────────────────────────────────────
  static const String _wsBaseUrl = 'ws://192.168.1.27:8000'; // Change in production

  // ── Dio instance for the local backend ────────────────────────────────
  static final Dio _dio = Dio(BaseOptions(
    baseUrl: _baseUrl,
    connectTimeout: const Duration(seconds: 300),
    sendTimeout: const Duration(seconds: 300),
    receiveTimeout: const Duration(seconds: 300),
  ));

  // ── Endpoint paths ────────────────────────────────────────────────────
  static String _analyzePath(String sessionId) =>
      '/pose/analyze/$sessionId';

  static String _classifyPath(String sessionId) =>
      '/pose/classify/$sessionId';

  static String _uploadPath(String sessionId) =>
      '/pose/upload/$sessionId';

  static String _historyPath(String sessionId) =>
      '/pose/history/$sessionId';

  static String _livePath(String sessionId, String exercise) =>
      '/pose/live/$sessionId?exercise=${Uri.encodeComponent(exercise)}';

  static String _streamAnalyzePath(
    String sessionId,
    String exerciseName,
    String videoId,
  ) =>
      '/pose/stream-analyze/$sessionId'
      '?exercise_name=${Uri.encodeComponent(exerciseName)}'
      '&video_id=${Uri.encodeComponent(videoId)}';

  static const String _exercisesPath = '/pose/exercises';
  static const String _classifierClassesPath = '/pose/classifier/classes';

  // ── Public API ────────────────────────────────────────────────────────

  /// Connect to the live pose estimation WebSocket.
  ///
  /// Returns a [WebSocketChannel] that:
  /// - **accepts** binary JPEG frames via `channel.sink.add(Uint8List)`
  /// - **emits** JSON text messages via `channel.stream` with per-frame
  ///   results: `{is_good_form, feedback_messages, rep_count, form_score, landmarks}`.
  ///
  /// Close the channel when the session ends to trigger the server-side
  /// summary storage.
  static WebSocketChannel connectLive({
    required String sessionId,
    required String exerciseName,
  }) {
    final uri = Uri.parse('$_wsBaseUrl${_livePath(sessionId, exerciseName)}');
    return WebSocketChannel.connect(uri);
  }

  /// Upload a video file for subsequent streaming analysis.
  ///
  /// Returns the `video_id` string used to initiate a streaming session.
  /// On **mobile/desktop**, pass [videoFilePath].
  /// On **web**, pass [videoBytes] and [videoFileName].
  static Future<String> uploadVideo({
    required String sessionId,
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
      videoFile = MultipartFile.fromBytes(
        videoBytes!,
        filename: videoFileName ?? 'upload.mp4',
      );
    } else {
      videoFile = await MultipartFile.fromFile(
        videoFilePath!,
        filename: videoFilePath.split('/').last,
      );
    }

    final formData = FormData.fromMap({'video': videoFile});

    final response = await _dio.post(
      _uploadPath(sessionId),
      data: formData,
      options: Options(contentType: 'multipart/form-data'),
    );

    final data = Map<String, dynamic>.from(response.data as Map);
    return data['video_id'] as String;
  }

  /// Connect to the streaming pose analysis WebSocket.
  ///
  /// Returns a [WebSocketChannel] whose stream emits:
  /// - **Text** messages (JSON) with `type` field:
  ///   - `frame` — per-frame metadata (index, total, form score, feedback)
  ///   - `form_correction` — voice-feedback alert
  ///   - `complete` — final report
  /// - **Binary** messages: JPEG-encoded annotated frames
  ///
  /// The client does **not** send any messages after connecting.
  static WebSocketChannel connectStreamAnalyze({
    required String sessionId,
    required String exerciseName,
    required String videoId,
  }) {
    final uri = Uri.parse(
      '$_wsBaseUrl${_streamAnalyzePath(sessionId, exerciseName, videoId)}',
    );
    return WebSocketChannel.connect(uri);
  }

  /// Upload a short video clip for automatic exercise classification.
  ///
  /// Returns `{"predicted_exercise": "...", "confidence": 0.97}`.
  /// On **mobile/desktop**, pass [videoFilePath].
  /// On **web**, pass [videoBytes] and [videoFileName].
  static Future<Map<String, dynamic>> classifyExercise({
    required String sessionId,
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
      videoFile = MultipartFile.fromBytes(
        videoBytes!,
        filename: videoFileName ?? 'upload.mp4',
      );
    } else {
      videoFile = await MultipartFile.fromFile(
        videoFilePath!,
        filename: videoFilePath.split('/').last,
      );
    }

    final formData = FormData.fromMap({
      'video': videoFile,
    });

    final response = await _dio.post(
      _classifyPath(sessionId),
      data: formData,
      options: Options(contentType: 'multipart/form-data'),
    );

    return Map<String, dynamic>.from(response.data as Map);
  }

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

  /// Get the list of supported exercise names (for form evaluation).
  static Future<List<String>> getSupportedExercises() async {
    final response = await _dio.get(_exercisesPath);
    return List<String>.from(response.data as List);
  }

  /// Get the 20-class taxonomy used by the exercise classifier.
  static Future<List<String>> getClassifierClasses() async {
    final response = await _dio.get(_classifierClassesPath);
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
