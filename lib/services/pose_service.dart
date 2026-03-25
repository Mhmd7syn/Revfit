import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:image_picker/image_picker.dart' show XFile;
import 'package:gym2/services/dio_helper.dart';

class PoseAnalysisResult {
  final String sessionId;
  final String exerciseName;
  final int totalFrames;
  final int badFrames;
  final int repCount;
  final double goodFormPercent;
  final List<PoseFeedback> feedbacks;
  final String annotatedVideoUrl;
  final String status;

  PoseAnalysisResult({
    required this.sessionId,
    required this.exerciseName,
    required this.totalFrames,
    required this.badFrames,
    required this.repCount,
    required this.goodFormPercent,
    required this.feedbacks,
    required this.annotatedVideoUrl,
    required this.status,
  });

  factory PoseAnalysisResult.fromJson(Map<String, dynamic> json) {
    return PoseAnalysisResult(
      sessionId: json['session_id'] ?? '',
      exerciseName: json['exercise_name'] ?? '',
      totalFrames: json['total_frames'] ?? 0,
      badFrames: json['bad_frames'] ?? 0,
      repCount: json['rep_count'] ?? 0,
      goodFormPercent: (json['good_form_percent'] ?? 0.0).toDouble(),
      feedbacks: (json['feedbacks'] as List<dynamic>? ?? [])
          .map((f) => PoseFeedback.fromJson(f))
          .toList(),
      annotatedVideoUrl: json['annotated_video_url'] ?? '',
      status: json['status'] ?? 'completed',
    );
  }
}

class PoseFeedback {
  final String message;
  final int occurrenceCount;
  final String metricType;
  final double? avgValue;

  PoseFeedback({
    required this.message,
    required this.occurrenceCount,
    required this.metricType,
    this.avgValue,
  });

  factory PoseFeedback.fromJson(Map<String, dynamic> json) {
    return PoseFeedback(
      message: json['message'] ?? '',
      occurrenceCount: json['occurrence_count'] ?? 0,
      metricType: json['metric_type'] ?? 'angle',
      avgValue: (json['avg_value'] as num?)?.toDouble(),
    );
  }
}

class PoseService {
  static const String _baseUrl = DioHelper.poseBaseUrl;

  /// Fetch all supported exercise names from the API
  static Future<List<String>> getExercises() async {
    try {
      final response = await DioHelper.getData(path: '$_baseUrl/api/pose/exercises');
      final data = response.data as Map<String, dynamic>;
      return List<String>.from(data['exercises'] ?? []);
    } catch (e) {
      throw Exception('Failed to fetch exercises: $e');
    }
  }

  /// Upload a video and analyse it. [onSendProgress] reports 0.0–1.0 upload progress.
  static Future<PoseAnalysisResult> analyzeVideo({
    required XFile videoFile,
    required String exerciseName,
    void Function(double progress)? onSendProgress,
  }) async {
    try {
      final MultipartFile file;
      if (kIsWeb) {
        final bytes = await videoFile.readAsBytes();
        file = MultipartFile.fromBytes(bytes, filename: videoFile.name);
      } else {
        file = await MultipartFile.fromFile(
          videoFile.path,
          filename: videoFile.name,
        );
      }

      final formData = FormData.fromMap({
        'exercise_name': exerciseName,
        'video': file,
      });

      final response = await DioHelper.postData(
        path: '$_baseUrl/api/pose/analyze',
        data: formData,
        onSendProgress: onSendProgress != null
            ? (sent, total) {
                if (total > 0) onSendProgress(sent / total);
              }
            : null,
      );

      return PoseAnalysisResult.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      final msg = e.response?.data?['detail'] ?? e.message ?? 'Unknown error';
      throw Exception('Analysis failed: $msg');
    }
  }

  /// Download the annotated video and save it to [savePath]. Returns the saved path.
  static Future<String> downloadAnnotatedVideo({
    required String sessionId,
    required String savePath,
    void Function(double progress)? onReceiveProgress,
  }) async {
    try {
      await DioHelper.download(
        path: '$_baseUrl/api/pose/download/$sessionId',
        savePath: savePath,
        onReceiveProgress: onReceiveProgress != null
            ? (received, total) {
                if (total > 0) onReceiveProgress(received / total);
              }
            : null,
      );
      return savePath;
    } catch (e) {
      throw Exception('Download failed: $e');
    }
  }

  /// Get the full analysis result JSON for a previous session.
  static Future<PoseAnalysisResult> getResult(String sessionId) async {
    try {
      final response = await DioHelper.getData(
        path: '$_baseUrl/api/pose/result/$sessionId',
      );
      return PoseAnalysisResult.fromJson(response.data as Map<String, dynamic>);
    } catch (e) {
      throw Exception('Failed to get result: $e');
    }
  }

  /// Returns the full download URL for a session's annotated video.
  static String videoDownloadUrl(String sessionId) =>
      '$_baseUrl/api/pose/download/$sessionId';
}
