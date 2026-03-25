import 'package:dio/dio.dart';
import 'package:dio/io.dart';
import 'package:flutter/foundation.dart' show kIsWeb;

class DioHelper {
  static late Dio _dio;

  // Centralized URLs for services
  static const String recommenderBaseUrl = 'http://127.0.0.1:8000';
  static const String poseBaseUrl = 'http://127.0.0.1:8000';
  static const String chatbotBaseUrl =
      'https://marcy-palmitic-dialectologically.ngrok-free.dev';

  static const String baseUrl = poseBaseUrl; // Default

  static init() {
    BaseOptions baseOptions = BaseOptions(
      baseUrl: baseUrl,
      // receiveDataWhenStatusError: true,
      // connectTimeout: const Duration(seconds: 30),
      // receiveTimeout: const Duration(seconds: 30),
      // sendTimeout: const Duration(seconds: 30),
      headers: {
        'Content-Type': 'application/json',
        // 'Accept': 'text/event-stream',   // removed – backend does not stream
      },
    );

    _dio = Dio(baseOptions);

    // Platform-specific configuration
    if (!kIsWeb) {
      // Only for mobile/desktop platforms
      (_dio.httpClientAdapter as IOHttpClientAdapter).onHttpClientCreate =
          (client) {
            client.badCertificateCallback = (cert, host, port) =>
                true; // For ngrok self-signed certificates
            return client;
          };
    }

    // Add interceptors for logging (optional)
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          print('REQUEST[${options.method}] => PATH: ${options.path}');
          return handler.next(options);
        },
        onResponse: (response, handler) {
          print('RESPONSE[${response.statusCode}] => DATA: ${response.data}');
          return handler.next(response);
        },
        onError: (DioException e, handler) {
          print('ERROR[${e.response?.statusCode}] => MESSAGE: ${e.message}');
          return handler.next(e);
        },
      ),
    );
  }

  static Future<Response> postData({
    required String path,
    required dynamic data,
    void Function(int, int)? onSendProgress,
    Options? options,
  }) async {
    return await _dio.post(
      path,
      data: data,
      onSendProgress: onSendProgress,
      options: options,
    );
  }

  static Future<Response> getData({
    required String path,
    Map<String, dynamic>? queryParameters,
    void Function(int, int)? onReceiveProgress,
    Options? options,
  }) async {
    return await _dio.get(
      path,
      queryParameters: queryParameters,
      onReceiveProgress: onReceiveProgress,
      options: options,
    );
  }

  static Future<Response> putData({
    required String path,
    required dynamic data,
    void Function(int, int)? onSendProgress,
    Options? options,
  }) async {
    return await _dio.put(
      path,
      data: data,
      onSendProgress: onSendProgress,
      options: options,
    );
  }

  static Future<Response> deleteData({
    required String path,
    Options? options,
  }) async {
    return await _dio.delete(path, options: options);
  }

  static Future<Response> download({
    required String path,
    required String savePath,
    void Function(int, int)? onReceiveProgress,
    Options? options,
  }) async {
    return await _dio.download(
      path,
      savePath,
      onReceiveProgress: onReceiveProgress,
      options: options,
    );
  }

  static Dio get dio => _dio;
}
