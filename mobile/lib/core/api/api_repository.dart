import 'dart:io';

import 'package:dio/dio.dart';

import 'api_client.dart';

class ApiRepository {
  ApiRepository(this._client);

  final ApiClient _client;

  Future<List<Map<String, dynamic>>> fetchList(
    String endpoint, {
    Map<String, dynamic>? params,
  }) async {
    final response = await _client.get(
      _normalize(endpoint),
      queryParameters: params,
    );
    final data = response.data;
    if (data is Map<String, dynamic>) {
      final results = data['results'];
      if (results is List) {
        return results.cast<Map<String, dynamic>>();
      }
      return [data];
    }
    if (data is List) {
      return data.cast<Map<String, dynamic>>();
    }
    return [];
  }

  Future<Map<String, dynamic>> fetchObject(String endpoint) async {
    final response = await _client.get(_normalize(endpoint));
    final data = response.data;
    if (data is Map<String, dynamic>) {
      return data;
    }
    return {'value': data};
  }

  Future<Map<String, dynamic>> fetchDetail(String endpoint, int id) async {
    final response = await _client.get('${_normalize(endpoint)}$id/');
    final data = response.data;
    if (data is Map<String, dynamic>) {
      return data;
    }
    return {'value': data};
  }

  String _normalize(String endpoint) {
    var trimmed = endpoint.startsWith('/') ? endpoint.substring(1) : endpoint;
    if (!trimmed.endsWith('/')) {
      trimmed = '$trimmed/';
    }
    return trimmed;
  }

  Future<Response<dynamic>> post(String endpoint, Object data) {
    return _client.post(_normalize(endpoint), data: data);
  }

  Future<Map<String, dynamic>> create(
    String endpoint,
    Map<String, dynamic> data,
  ) async {
    final response = await _client.post(_normalize(endpoint), data: data);
    return (response.data as Map<String, dynamic>?) ?? {};
  }

  Future<Map<String, dynamic>> update(
    String endpoint,
    int id,
    Map<String, dynamic> data,
  ) async {
    final response = await _client.put(
      '${_normalize(endpoint)}$id/',
      data: data,
    );
    return (response.data as Map<String, dynamic>?) ?? {};
  }

  Future<Map<String, dynamic>> patch(
    String endpoint,
    int id,
    Map<String, dynamic> data,
  ) async {
    final response = await _client.patch(
      '${_normalize(endpoint)}$id/',
      data: data,
    );
    return (response.data as Map<String, dynamic>?) ?? {};
  }

  Future<void> delete(String endpoint, int id) async {
    await _client.delete('${_normalize(endpoint)}$id/');
  }

  Future<Map<String, dynamic>> uploadFile({
    required String endpoint,
    required Map<String, dynamic> fields,
    required File file,
    String fileField = 'file',
  }) async {
    final formData = FormData.fromMap({
      ...fields,
      fileField: await MultipartFile.fromFile(file.path),
    });
    final response = await _client.post(_normalize(endpoint), data: formData);
    return (response.data as Map<String, dynamic>?) ?? {};
  }
}
