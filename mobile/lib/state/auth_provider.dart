import 'package:dio/dio.dart'; // <-- ADD THIS LINE
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../api/client.dart';


class AuthState {
  final bool isAuthenticated;
  final bool isLoading;
  final String? error;
  const AuthState({this.isAuthenticated = false, this.isLoading = false, this.error});

  AuthState copyWith({bool? isAuthenticated, bool? isLoading, String? error}) {
    return AuthState(
      isAuthenticated: isAuthenticated ?? this.isAuthenticated,
      isLoading: isLoading ?? this.isLoading,
      error: error,
    );
  }
}

class AuthNotifier extends StateNotifier<AuthState> {
  final _storage = const FlutterSecureStorage();
  AuthNotifier() : super(const AuthState()) { _checkToken(); }

  Future<void> _checkToken() async {
    final token = await _storage.read(key: 'api_token');
    if (token != null) {
      state = state.copyWith(isAuthenticated: true);
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
      state = state.copyWith(isAuthenticated: true, isLoading: false);
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
    await _storage.delete(key: 'api_token');
    state = const AuthState(isAuthenticated: false);
  }
}

final authProvider = StateNotifierProvider<AuthNotifier, AuthState>((ref) => AuthNotifier());
