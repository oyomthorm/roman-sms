import 'package:dio/dio.dart';
import 'dart:async';
import 'dart:math';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:intl/intl.dart';
import '../api/client.dart';
import '../theme/app_theme.dart';
import '../state/providers.dart';

class NewCampaignScreen extends ConsumerStatefulWidget {
  const NewCampaignScreen({super.key});

  @override
  ConsumerState<NewCampaignScreen> createState() => _NewCampaignScreenState();
}

class _NewCampaignScreenState extends ConsumerState<NewCampaignScreen> {
  final _nameController = TextEditingController();
  final _bodyController = TextEditingController();
  final _pasteController = TextEditingController();
  
  String _recipientSource = 'contacts'; // 'contacts' or 'paste'
  Map<String, dynamic>? _previewData;
  Timer? _debounce;
  bool _isSubmitting = false;

  @override
  void initState() {
    super.initState();
    _bodyController.addListener(_schedulePreview);
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _nameController.dispose();
    _bodyController.dispose();
    _pasteController.dispose();
    super.dispose();
  }

  void _schedulePreview() {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 400), _fetchPreview);
  }

  Future<void> _fetchPreview() async {
    if (_bodyController.text.isEmpty) {
      setState(() => _previewData = null);
      return;
    }
    try {
      final r = await ApiClient.instance.dio.post(
        '/api/v1/campaigns/preview',
        data: {'body': _bodyController.text},
      );
      if (mounted) setState(() => _previewData = r.data);
    } catch (_) {
      // Ignore preview errors, usually just network blips during typing
    }
  }

  String _generateIdempotencyKey() {
    final r = Random.secure();
    return List.generate(16, (_) => r.nextInt(256).toRadixString(16).padLeft(2, '0')).join();
  }

  Future<void> _submitCampaign() async {
    if (_bodyController.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Message body is required')));
      return;
    }

    setState(() => _isSubmitting = true);
    try {
      final payload = {
        'name': _nameController.text.trim(),
        'body': _bodyController.text,
        'recipient_source': _recipientSource,
        if (_recipientSource == 'paste') 'pasted_numbers': _pasteController.text,
      };

      final r = await ApiClient.instance.dio.post(
        '/api/v1/campaigns',
        data: payload,
        options: Options(headers: {'Idempotency-Key': _generateIdempotencyKey()}),
      );

      if (mounted) {
        // Refresh wallet balance since it was just debited
        ref.invalidate(walletProvider);
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Campaign created successfully!')));
        context.go('/'); // Go back home
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Failed to create campaign. Check balance or inputs.')));
      }
    } finally {
      if (mounted) setState(() => _isSubmitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final currencyFormat = NumberFormat.currency(locale: 'en_UG', symbol: 'UGX ', decimalDigits: 0);

    return Scaffold(
      appBar: AppBar(
        title: Text('New Campaign', style: GoogleFonts.inter(fontWeight: FontWeight.bold)),
        backgroundColor: Colors.transparent,
        elevation: 0,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 1. Campaign Details
            Text('Campaign Details', style: GoogleFonts.inter(fontSize: 16, fontWeight: FontWeight.bold)),
            const SizedBox(height: 12),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  children: [
                    TextField(
                      controller: _nameController,
                      decoration: const InputDecoration(
                        labelText: 'Campaign Name (Optional)',
                        border: OutlineInputBorder(),
                      ),
                    ),
                    const SizedBox(height: 16),
                    TextField(
                      controller: _bodyController,
                      maxLines: 4,
                      decoration: const InputDecoration(
                        labelText: 'Message Body',
                        alignLabelWithHint: true,
                        border: OutlineInputBorder(),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 24),

            // 2. Recipients (Adapted from Mockup selectors)
            Text('Recipients', style: GoogleFonts.inter(fontSize: 16, fontWeight: FontWeight.bold)),
            const SizedBox(height: 12),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: RadioListTile<String>(
                            title: const Text('Contacts'),
                            value: 'contacts',
                            groupValue: _recipientSource,
                            onChanged: (v) => setState(() => _recipientSource = v!),
                            contentPadding: EdgeInsets.zero,
                          ),
                        ),
                        Expanded(
                          child: RadioListTile<String>(
                            title: const Text('Paste Numbers'),
                            value: 'paste',
                            groupValue: _recipientSource,
                            onChanged: (v) => setState(() => _recipientSource = v!),
                            contentPadding: EdgeInsets.zero,
                          ),
                        ),
                      ],
                    ),
                    if (_recipientSource == 'paste') ...[
                      const Divider(),
                      const SizedBox(height: 8),
                      TextField(
                        controller: _pasteController,
                        maxLines: 5,
                        decoration: const InputDecoration(
                          hintText: 'One phone number per line (e.g., 0700123456)',
                          border: OutlineInputBorder(),
                        ),
                      ),
                    ] else ...[
                      const Divider(),
                      ListTile(
                        leading: const Icon(Icons.group, color: RomanSmsTheme.primaryGreen),
                        title: const Text('All Contacts'),
                        subtitle: const Text('Send to everyone (excluding opt-outs)'),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () {}, // Future: group selector modal
                      ),
                    ],
                  ],
                ),
              ),
            ),
            const SizedBox(height: 24),

            // 3. Cost Preview (Matches Mockup "Loan Details" card)
            if (_previewData != null) ...[
              Text('Cost Breakdown', style: GoogleFonts.inter(fontSize: 16, fontWeight: FontWeight.bold)),
              const SizedBox(height: 12),
              Card(
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(16),
                  side: const BorderSide(color: Color(0xFFE2E8F0)),
                ),
                child: Column(
                  children: [
                    Padding(
                      padding: const EdgeInsets.all(16),
                      child: Row(
                        children: [
                          const Icon(Icons.text_fields, color: RomanSmsTheme.textMuted),
                          const SizedBox(width: 12),
                          Text('Characters & Segments', style: GoogleFonts.inter(fontSize: 14)),
                          const Spacer(),
                          Text(
                            '${_previewData!['characters']} chars Â· ${_previewData!['segments']} SMS',
                            style: GoogleFonts.inter(fontWeight: FontWeight.bold, color: RomanSmsTheme.textDark),
                          ),
                        ],
                      ),
                    ),
                    const Divider(height: 1),
                    Padding(
                      padding: const EdgeInsets.all(16),
                      child: Row(
                        children: [
                          const Icon(Icons.payments_outlined, color: RomanSmsTheme.textMuted),
                          const SizedBox(width: 12),
                          Text('Estimated Cost', style: GoogleFonts.inter(fontSize: 14)),
                          const Spacer(),
                          Text(
                            currencyFormat.format(_previewData!['cost_ugx']),
                            style: GoogleFonts.inter(fontWeight: FontWeight.bold, fontSize: 18, color: RomanSmsTheme.primaryGreen),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 24),
            ],

            // 4. Submit Button
            SizedBox(
              width: double.infinity,
              height: 56,
              child: ElevatedButton(
                onPressed: _isSubmitting ? null : _submitCampaign,
                style: ElevatedButton.styleFrom(
                  backgroundColor: RomanSmsTheme.primaryGreen,
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                ),
                child: _isSubmitting
                    ? const CircularProgressIndicator(color: Colors.white)
                    : Text(
                        'Send Campaign',
                        style: GoogleFonts.inter(fontSize: 16, fontWeight: FontWeight.bold),
                      ),
              ),
            ),
            const SizedBox(height: 40),
          ],
        ),
      ),
    );
  }
}

