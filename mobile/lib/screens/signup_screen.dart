import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:google_fonts/google_fonts.dart';
import '../api/client.dart';
import '../theme/app_theme.dart';

class SignupScreen extends ConsumerStatefulWidget {
  const SignupScreen({super.key});
  @override
  ConsumerState<SignupScreen> createState() => _SignupScreenState();
}

class _SignupScreenState extends ConsumerState<SignupScreen> {
  final _formKey = GlobalKey<FormState>();

  final _companyCtrl = TextEditingController();
  final _nameCtrl = TextEditingController();
  final _emailCtrl = TextEditingController();
  final _phoneCtrl = TextEditingController();
  final _slugCtrl = TextEditingController();
  final _brandCtrl = TextEditingController();
  final _volumeCtrl = TextEditingController();
  final _messageCtrl = TextEditingController();

  bool _submitting = false;
  String? _error;

  @override
  void dispose() {
    _companyCtrl.dispose();
    _nameCtrl.dispose();
    _emailCtrl.dispose();
    _phoneCtrl.dispose();
    _slugCtrl.dispose();
    _brandCtrl.dispose();
    _volumeCtrl.dispose();
    _messageCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    setState(() => _error = null);
    if (!(_formKey.currentState?.validate() ?? false)) return;

    setState(() => _submitting = true);

    try {
      final resp = await ApiClient.instance.submitSignup(
        companyName: _companyCtrl.text.trim(),
        desiredSlug: _slugCtrl.text.trim().toLowerCase(),
        contactName: _nameCtrl.text.trim(),
        contactEmail: _emailCtrl.text.trim().toLowerCase(),
        brandName:
            _brandCtrl.text.trim().isEmpty ? null : _brandCtrl.text.trim(),
        contactPhone:
            _phoneCtrl.text.trim().isEmpty ? null : _phoneCtrl.text.trim(),
        expectedVolume:
            _volumeCtrl.text.trim().isEmpty ? null : _volumeCtrl.text.trim(),
        message:
            _messageCtrl.text.trim().isEmpty ? null : _messageCtrl.text.trim(),
      );

      debugPrint('=== SIGNUP RESPONSE ===');
      debugPrint('status: ${resp.statusCode}');
      debugPrint('body: ${resp.data}');
      debugPrint('=======================');

      if (resp.statusCode == 200 || resp.statusCode == 201) {
        if (mounted) context.go('/signup/pending');
        return;
      }
      setState(() => _error = 'Unexpected response (${resp.statusCode}).');
    } catch (e) {
      debugPrint('=== SIGNUP EXCEPTION ===');
      debugPrint('runtimeType: ${e.runtimeType}');
      debugPrint('toString:    $e');
      if (e is DioException) {
        debugPrint('dio.type:    ${e.type}');
        debugPrint('dio.error:   ${e.error}');
        debugPrint('dio.message: ${e.message}');
        debugPrint('dio.status:  ${e.response?.statusCode}');
        debugPrint('dio.body:    ${e.response?.data}');
        debugPrint('dio.uri:     ${e.requestOptions.uri}');
      }
      debugPrint('========================');

      String msg;
      if (e is DioException) {
        if (e.response != null) {
          // Server responded with a 4xx/5xx — extract the JSON message if present.
          final data = e.response!.data;
          if (data is Map && data['message'] is String) {
            msg = data['message'] as String;
          } else if (data is Map && data['error'] is String) {
            msg = data['error'] as String;
          } else {
            msg = 'Server error (${e.response!.statusCode}).';
          }
        } else if (e.type == DioExceptionType.connectionTimeout) {
          msg = 'Network timeout. Check your internet connection.';
        } else if (e.type == DioExceptionType.connectionError) {
          msg = 'Cannot reach the server. Check your internet connection.';
        } else if (e.type == DioExceptionType.unknown) {
          msg = 'Network error: ${e.error ?? e.message ?? "unknown"}.';
        } else {
          msg = 'Network error: ${e.type.name}.';
        }
      } else {
        msg = 'Unexpected error: ${e.runtimeType}.';
      }
      setState(() => _error = msg);
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(
          'Apply for an account',
          style: GoogleFonts.inter(fontWeight: FontWeight.w600),
        ),
        backgroundColor: RomanSmsTheme.primaryGreen,
        foregroundColor: Colors.white,
      ),
      body: SafeArea(
        child: Form(
          key: _formKey,
          child: ListView(
            padding: const EdgeInsets.all(20),
            children: [
              Text(
                'Tell us about your business. We review every application '
                'manually and reply within one working day.',
                style: GoogleFonts.inter(
                  fontSize: 14,
                  color: RomanSmsTheme.textMuted,
                ),
              ),
              const SizedBox(height: 24),
              _field(
                controller: _companyCtrl,
                label: 'Company name',
                icon: Icons.business_outlined,
                required: true,
              ),
              const SizedBox(height: 12),
              _field(
                controller: _nameCtrl,
                label: 'Your full name',
                icon: Icons.person_outline,
                required: true,
              ),
              const SizedBox(height: 12),
              _field(
                controller: _emailCtrl,
                label: 'Email',
                icon: Icons.email_outlined,
                keyboard: TextInputType.emailAddress,
                required: true,
                validator: (v) {
                  if (v == null || v.trim().isEmpty) return 'Email is required';
                  if (!v.contains('@') || !v.contains('.')) {
                    return 'Enter a valid email';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 12),
              _field(
                controller: _phoneCtrl,
                label: 'Phone (optional)',
                icon: Icons.phone_outlined,
                keyboard: TextInputType.phone,
                required: false,
              ),
              const SizedBox(height: 12),
              _field(
                controller: _slugCtrl,
                label: 'URL slug',
                icon: Icons.link,
                required: true,
                helper: '3–50 chars, lowercase letters, numbers, dashes. '
                    'E.g. "acme-traders".',
                validator: (v) {
                  final s = (v ?? '').trim().toLowerCase();
                  if (s.isEmpty) return 'Slug is required';
                  if (!RegExp(r'^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$')
                      .hasMatch(s)) {
                    return 'Invalid slug format';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 12),
              _field(
                controller: _brandCtrl,
                label: 'Brand prefix (optional, max 20 chars)',
                icon: Icons.label_outline,
                required: false,
                maxLength: 20,
                helper: 'Shown before every message, e.g. "ACME: ".',
              ),
              const SizedBox(height: 12),
              _field(
                controller: _volumeCtrl,
                label: 'Expected volume (optional)',
                icon: Icons.trending_up,
                required: false,
                helper: 'E.g. "5,000 SMS per month".',
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _messageCtrl,
                minLines: 3,
                maxLines: 5,
                decoration: const InputDecoration(
                  labelText: 'Anything else (optional)',
                  border: OutlineInputBorder(),
                  alignLabelWithHint: true,
                ),
              ),
              if (_error != null) ...[
                const SizedBox(height: 16),
                Text(
                  _error!,
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: Colors.red),
                ),
              ],
              const SizedBox(height: 24),
              ElevatedButton(
                onPressed: _submitting ? null : _submit,
                style: ElevatedButton.styleFrom(
                  backgroundColor: RomanSmsTheme.primaryGreen,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                child: _submitting
                    ? const SizedBox(
                        height: 20,
                        width: 20,
                        child: CircularProgressIndicator(
                          color: Colors.white,
                          strokeWidth: 2,
                        ),
                      )
                    : Text(
                        'Submit application',
                        style: GoogleFonts.inter(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
              ),
              const SizedBox(height: 12),
              TextButton(
                onPressed: _submitting ? null : () => context.go('/login'),
                child: const Text('Already have an account? Sign in'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _field({
    required TextEditingController controller,
    required String label,
    required IconData icon,
    required bool required,
    TextInputType? keyboard,
    String? helper,
    int? maxLength,
    String? Function(String?)? validator,
  }) {
    return TextFormField(
      controller: controller,
      keyboardType: keyboard,
      maxLength: maxLength,
      decoration: InputDecoration(
        labelText: label,
        helperText: helper,
        helperMaxLines: 3,
        border: const OutlineInputBorder(),
        prefixIcon: Icon(icon),
      ),
      validator: validator ??
          (required
              ? (v) =>
                  (v == null || v.trim().isEmpty) ? '$label is required' : null
              : null),
    );
  }
}
