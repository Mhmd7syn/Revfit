import 'dart:convert';
import 'package:dio/dio.dart';
import 'dio_helper.dart';
import 'package:flutter/foundation.dart' show kIsWeb;

class ChatBotServices {
  static const String chatEndpoint = '/chat';

  // Stream chat responses
  static Stream<Map<String, dynamic>> streamChat(String message) async* {
    try {
      final data = {'message': message};

      final response = await DioHelper.dio.post(
        '${DioHelper.chatbotBaseUrl}${ChatBotServices.chatEndpoint}',
        data: data,
        options: Options(
          responseType: ResponseType.stream,
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'text/event-stream',
          },
        ),
      );

      final stream = response.data as ResponseBody;

      await for (var chunk in stream.stream) {
        final chunkStr = utf8.decode(chunk);
        print('Raw chunk: $chunkStr'); // For debugging

        // Split by double newline (SSE format)
        final events = chunkStr.split('\n\n');

        for (var event in events) {
          if (event.isNotEmpty) {
            final lines = event.split('\n');
            for (var line in lines) {
              if (line.startsWith('data: ')) {
                final jsonStr = line.substring(6); // Remove 'data: ' prefix
                try {
                  final jsonData = json.decode(jsonStr);

                  if (jsonData.containsKey('token')) {
                    yield {'type': 'token', 'content': jsonData['token']};
                  } else if (jsonData.containsKey('final')) {
                    yield {
                      'type': 'final',
                      'reply': jsonData['reply'],
                      'intent': jsonData['intent'],
                      'route': jsonData['route'],
                    };
                  }
                } catch (e) {
                  print('Error parsing JSON: $e');
                }
              }
            }
          }
        }
      }
    } on DioException catch (e) {
      print('DioException: $e');
      String errorMessage = 'Connection error';

      if (e.type == DioExceptionType.connectionTimeout) {
        errorMessage = 'Connection timeout. Please check your internet.';
      } else if (e.type == DioExceptionType.receiveTimeout) {
        errorMessage = 'Server is taking too long to respond.';
      } else if (e.type == DioExceptionType.connectionError) {
        errorMessage = 'No internet connection.';
      } else if (e.response != null) {
        errorMessage = 'Server error: ${e.response?.statusCode}';
      }

      yield {'type': 'error', 'content': errorMessage};
    } catch (e) {
      print('Unexpected error: $e');
      yield {'type': 'error', 'content': 'Unexpected error: $e'};
    }
  }
}
