import 'package:dio/dio.dart';

import '../auth/token_storage.dart';
import '../config/app_config.dart';

class ApiClient {
  ApiClient(this._storage) {
    _dio = Dio(
      BaseOptions(
        baseUrl: AppConfig.apiBaseUrl,
        connectTimeout: const Duration(seconds: 20),
        receiveTimeout: const Duration(seconds: 20),
        headers: {'Accept': 'application/json'},
      ),
    );

    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          final path = options.path;
          final isAuthEndpoint =
              path.contains('auth/token') || path.contains('auth/refresh');
          final token = _storage.accessToken;
          if (!isAuthEndpoint && token != null && token.isNotEmpty) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          handler.next(options);
        },
        onError: (error, handler) {
          if (error.response?.statusCode == 401 && _onUnauthorized != null) {
            _onUnauthorized?.call();
          }
          handler.next(error);
        },
      ),
    );
  }

  final TokenStorage _storage;
  late final Dio _dio;
  void Function()? _onUnauthorized;

  void setUnauthorizedHandler(void Function() handler) {
    _onUnauthorized = handler;
  }

  Future<Response<dynamic>> get(
    String path, {
    Map<String, dynamic>? queryParameters,
  }) {
    return _dio.get(path, queryParameters: queryParameters);
  }

  Future<Response<dynamic>> post(
    String path, {
    Object? data,
    Map<String, dynamic>? queryParameters,
  }) {
    return _dio.post(path, data: data, queryParameters: queryParameters);
  }

  Future<Response<dynamic>> put(
    String path, {
    Object? data,
    Map<String, dynamic>? queryParameters,
  }) {
    return _dio.put(path, data: data, queryParameters: queryParameters);
  }

  Future<Response<dynamic>> patch(
    String path, {
    Object? data,
    Map<String, dynamic>? queryParameters,
  }) {
    return _dio.patch(path, data: data, queryParameters: queryParameters);
  }

  Future<Response<dynamic>> delete(
    String path, {
    Object? data,
    Map<String, dynamic>? queryParameters,
  }) {
    return _dio.delete(path, data: data, queryParameters: queryParameters);
  }
}
