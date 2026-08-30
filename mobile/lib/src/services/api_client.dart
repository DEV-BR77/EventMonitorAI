import 'dart:convert';

import 'package:http/http.dart' as http;

import '../domain/measurement.dart';

class ApiException implements Exception {
  const ApiException(this.message);
  final String message;
  @override
  String toString() => message;
}

class LoginResult {
  const LoginResult({
    required this.token,
    required this.tenantId,
    required this.tenantName,
    required this.username,
  });
  final String token;
  final int tenantId;
  final String tenantName;
  final String username;
}

class ApiClient {
  ApiClient({http.Client? client}) : _client = client ?? http.Client();
  final http.Client _client;

  Future<LoginResult> login(
    String baseUrl,
    String username,
    String password,
  ) async {
    final response = await _client.post(
      Uri.parse('${_normalized(baseUrl)}/auth/login'),
      headers: const {'content-type': 'application/json'},
      body: jsonEncode({'username': username, 'password': password}),
    );
    final body = _decode(response);
    return LoginResult(
      token: body['access_token'] as String,
      tenantId: body['tenant_id'] as int,
      tenantName: body['tenant_name'] as String,
      username: body['username'] as String,
    );
  }

  Future<List<Map<String, dynamic>>> devices(
    String baseUrl,
    String token,
  ) async {
    final response = await _client.get(
      Uri.parse('${_normalized(baseUrl)}/api/devices'),
      headers: _authorization(token),
    );
    final decoded = jsonDecode(response.body);
    if (response.statusCode >= 400 || decoded is! List) {
      throw ApiException(_message(decoded, response.statusCode));
    }
    return decoded.cast<Map<String, dynamic>>();
  }

  Future<List<MobileEvent>> events(String baseUrl, String token) async {
    final response = await _client.get(
      Uri.parse('${_normalized(baseUrl)}/events?limit=50'),
      headers: _authorization(token),
    );
    final decoded = jsonDecode(response.body);
    if (response.statusCode >= 400 || decoded is! List) {
      throw ApiException(_message(decoded, response.statusCode));
    }
    return decoded
        .cast<Map<String, dynamic>>()
        .map(MobileEvent.fromJson)
        .toList(growable: false);
  }

  Future<List<Map<String, dynamic>>> noiseLog(
    String baseUrl,
    String token,
  ) async {
    final response = await _client.get(
      Uri.parse('${_normalized(baseUrl)}/push/noise-log'),
      headers: _authorization(token),
    );
    final decoded = jsonDecode(response.body);
    if (response.statusCode >= 400 || decoded is! List) {
      throw ApiException(_message(decoded, response.statusCode));
    }
    return decoded.cast<Map<String, dynamic>>();
  }

  Map<String, dynamic> _decode(http.Response response) {
    final decoded = jsonDecode(response.body);
    if (response.statusCode >= 400 || decoded is! Map<String, dynamic>) {
      throw ApiException(_message(decoded, response.statusCode));
    }
    return decoded;
  }

  String _normalized(String value) {
    final uri = Uri.parse(value.trim());
    if (uri.scheme != 'https' || uri.host.isEmpty) {
      throw const ApiException(
        'Für Serververbindungen ist HTTPS erforderlich.',
      );
    }
    return value.trim().replaceFirst(RegExp(r'/$'), '');
  }

  Map<String, String> _authorization(String token) => {
    'authorization': 'Bearer $token',
    'accept': 'application/json',
  };

  String _message(Object? body, int status) =>
      body is Map && body['detail'] is String
      ? body['detail'] as String
      : 'Serveranfrage fehlgeschlagen ($status).';

  void close() => _client.close();
}
