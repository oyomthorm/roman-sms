import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../api/client.dart';

class AuthState {
  final bool isAuthenticated;
  final bool isLoading;
  final String? error;
  final Map<String, dynamic>? user;
  final Map<String, dynamic>? org;

  const AuthState({
    this.isAuthenticated = false,
    this.isLoading = false,
    this.error,
    this.user,
    this.org,
  });

  AuthState copyWith({
    bool? isAuthenticated,
    bool? isLoading,
    String? error,
    Map<String, dynamic>? user,
    Map<String, dynamic>? org,
    bool clearUser = false,
    bool clearOrg = false,
  }) {
    return AuthState(
      isAuthenticated: isAuthenticated ?? this.isAuthenticated,
      isLoading: isLoading ?? this.isLoading,
      error: error,
      user: clearUser ? null : (user ?? this.user),
      org: clearOrg ? null : (org ?? this.org),
    );
  }
}

class AuthNotifier extends StateNotifier<AuthState> {
  final _storage = const FlutterSecureStorage();
  AuthNotifier() : super(const AuthState()) {
    _checkToken();
  }

  Future<void> _checkToken() async {
    final token = await _storage.read(key: 'api_token');
    if (token == null) return;
    try {
      final r = await ApiClient.instance.dio.get('/api/v1/auth/me');
      state = state.copyWith(
        isAuthenticated: true,
        user: r.data['user'] as Map<String, dynamic>?,
        org: r.data['org'] as Map<String, dynamic>?,
      );
    } catch (_) {
      await _storage.delete(key: 'api_token');
      state = const AuthState(isAuthenticated: false);
    }
  }

  Future<bool> login(String email, String password) async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      final r = await ApiClient.instance.dio.post('/api/v1/auth/login', data: {
        'email': email,
        'password': password,
        'device_label': 'Flutter Android',
      });
      await _storage.write(key: 'api_token', value: r.data['token']);
      state = state.copyWith(
        isAuthenticated: true,
        isLoading: false,
        error: null,
        user: r.data['user'] as Map<String, dynamic>?,
        org: r.data['org'] as Map<String, dynamic>?,
      );
      return true;
    } catch (e) {
      String errMsg = "Unknown error";
      if (e is DioException) {
        if (e.type == DioExceptionType.connectionTimeout) {
          errMsg = "Connection Timeout. The phone cannot reach the laptop.";
        } else if (e.type == DioExceptionType.connectionError) {
          errMsg = "Connection Refused. Windows Firewall is blocking the port.";
        } else if (e.response != null) {
          errMsg = "Server returned error ${e.response?.statusCode}";
        } else {
          errMsg = e.message ?? "Network error";
        }
      }
      state = state.copyWith(isLoading: false, error: errMsg);
      return false;
    }
  }

  Future<void> logout() async {
    try {
      await ApiClient.instance.dio.post('/api/v1/auth/logout');
    } catch (_) {
      // Ignore — even if server revoke fails, we clear local state.
    }
    await _storage.delete(key: 'api_token');
    state = const AuthState(isAuthenticated: false);
  }

  Future<void> refreshProfile() async {
    try {
      final r = await ApiClient.instance.dio.get('/api/v1/auth/me');
      state = state.copyWith(
        user: r.data['user'] as Map<String, dynamic>?,
        org: r.data['org'] as Map<String, dynamic>?,
      );
    } catch (_) {
      // Silent — if refresh fails, keep existing state.
    }
  }
}

final authProvider =
    StateNotifierProvider<AuthNotifier, AuthState>((ref) => AuthNotifier());
