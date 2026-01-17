import 'dart:async';

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
    _refreshDio = Dio(
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
        onError: (error, handler) async {
          final statusCode = error.response?.statusCode;
          final requestOptions = error.requestOptions;
          final path = requestOptions.path;
          final isAuthEndpoint =
              path.contains('auth/token') || path.contains('auth/refresh');
          final wasRetried = requestOptions.extra['retried'] == true;
          if (statusCode == 401 && !isAuthEndpoint && !wasRetried) {
            final refreshed = await _refreshAccessToken();
            if (refreshed) {
              requestOptions.extra['retried'] = true;
              final accessToken = _storage.accessToken;
              if (accessToken != null && accessToken.isNotEmpty) {
                requestOptions.headers['Authorization'] =
                    'Bearer $accessToken';
              } else {
                requestOptions.headers.remove('Authorization');
              }
              try {
                final response = await _dio.fetch(requestOptions);
                handler.resolve(response);
                return;
              } on DioException catch (retryError) {
                handler.reject(retryError);
                return;
              }
            }
          }
          if (statusCode == 401 && !isAuthEndpoint && _onUnauthorized != null) {
            _onUnauthorized?.call();
          }
          handler.next(error);
        },
      ),
    );
  }

  final TokenStorage _storage;
  late final Dio _dio;
  late final Dio _refreshDio;
  void Function()? _onUnauthorized;
  bool _isRefreshing = false;
  Completer<bool>? _refreshCompleter;

  void setUnauthorizedHandler(void Function() handler) {
    _onUnauthorized = handler;
  }

  Future<bool> _refreshAccessToken() async {
    if (_isRefreshing) {
      return _refreshCompleter?.future ?? false;
    }
    final refreshToken = _storage.refreshToken;
    if (refreshToken == null || refreshToken.isEmpty) {
      return false;
    }
    _isRefreshing = true;
    _refreshCompleter = Completer<bool>();
    try {
      final response = await _refreshDio.post(
        'auth/refresh/',
        data: {'refresh': refreshToken},
      );
      if (response.data is! Map<String, dynamic>) {
        _refreshCompleter?.complete(false);
        return false;
      }
      final data = response.data as Map<String, dynamic>;
      final accessToken = data['access'] as String?;
      if (accessToken == null || accessToken.isEmpty) {
        _refreshCompleter?.complete(false);
        return false;
      }
      await _storage.save(accessToken: accessToken);
      if (data['refresh'] != null) {
        await _storage.save(refreshToken: data['refresh'] as String?);
      }
      _refreshCompleter?.complete(true);
      return true;
    } catch (_) {
      _refreshCompleter?.complete(false);
      return false;
    } finally {
      _isRefreshing = false;
    }
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
