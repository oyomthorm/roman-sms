import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class ApiClient {
  ApiClient._();
  static final instance = ApiClient._();

  final _storage = const FlutterSecureStorage();
  late final Dio dio = Dio(BaseOptions(
    baseUrl: 'https://romansms.com',
    connectTimeout: const Duration(seconds: 15),
    receiveTimeout: const Duration(seconds: 30),
    headers: {'Accept': 'application/json'},
  ))
    ..interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) async {
        final token = await _storage.read(key: 'api_token');
        if (token != null) options.headers['Authorization'] = 'Bearer $token';
        handler.next(options);
      },
    ));

  /// Submit a signup application. Anonymous endpoint — no token required.
  /// Returns the raw Dio response; the caller inspects status and body.
  /// Honeypot field `website` is always sent empty: the server drops any
  /// non-empty value as a bot (same rule as the web form).
  Future<Response<dynamic>> submitSignup({
    required String companyName,
    required String desiredSlug,
    required String contactName,
    required String contactEmail,
    String? brandName,
    String? contactPhone,
    int? districtId,
    int? planId,
    String? expectedVolume,
    String? message,
  }) {
    return dio.post('/api/v1/auth/signup', data: {
      'company_name': companyName,
      'desired_slug': desiredSlug,
      'contact_name': contactName,
      'contact_email': contactEmail,
      'brand_name': brandName,
      'contact_phone': contactPhone,
      'district_id': districtId,
      'plan_id': planId,
      'expected_volume': expectedVolume,
      'message': message,
      'website': '', // honeypot — always empty from a real client
    });
  }
}
