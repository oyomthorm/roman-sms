import 'package:dio/dio.dart';
import 'dart:math';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:intl/intl.dart';
import '../api/client.dart';
import '../theme/app_theme.dart';
import '../state/providers.dart';

class PlansScreen extends ConsumerStatefulWidget {
  const PlansScreen({super.key});
  @override
  ConsumerState<PlansScreen> createState() => _PlansScreenState();
}

class _PlansScreenState extends ConsumerState<PlansScreen> {
  bool _isProcessing = false;

  String _generateIdempotencyKey() {
    final r = Random.secure();
    return List.generate(16, (_) => r.nextInt(256).toRadixString(16).padLeft(2, '0')).join();
  }

  num _asNum(dynamic v) {
    if (v == null) return 0;
    if (v is num) return v;
    return num.tryParse(v.toString()) ?? 0;
  }

  Future<void> _buyPlan(int planId, String planName) async {
    setState(() => _isProcessing = true);
    try {
      await ApiClient.instance.dio.post(
        '/api/v1/invoices',
        data: {'plan_id': planId},
        options: Options(headers: {'Idempotency-Key': _generateIdempotencyKey()}),
      );
      if (mounted) {
        showDialog(
          context: context,
          builder: (ctx) => AlertDialog(
            title: const Text('Invoice Created'),
            content: Text('Your invoice for the $planName plan has been generated. Please check your email or the web portal for payment instructions.'),
            actions: [
              TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('OK')),
            ],
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Failed to create invoice.')));
      }
    } finally {
      if (mounted) setState(() => _isProcessing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final plansAsync = ref.watch(plansProvider);
    final walletAsync = ref.watch(walletProvider);
    final currencyFormat = NumberFormat.currency(locale: 'en_UG', symbol: 'UGX ', decimalDigits: 0);

    return Scaffold(
      appBar: AppBar(
        title: Text('Buy SMS Credits', style: GoogleFonts.inter(fontWeight: FontWeight.bold)),
        backgroundColor: Colors.transparent,
        elevation: 0,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Current Balance Summary
            walletAsync.when(
              loading: () => const SizedBox(),
              error: (_, __) => const SizedBox(),
              data: (wallet) => Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: RomanSmsTheme.lightGreen,
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.account_balance_wallet, color: RomanSmsTheme.primaryGreen),
                    const SizedBox(width: 12),
                    Text(
                      'Current Balance: ${wallet['balance']} SMS',
                      style: GoogleFonts.inter(fontWeight: FontWeight.bold, color: RomanSmsTheme.primaryGreen),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 24),
            
            Text('Select a Bundle', style: GoogleFonts.inter(fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 12),

            plansAsync.when(
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (e, _) => Center(child: Text('Error: $e')),
              data: (plans) {
                return Column(
                  children: plans.map((plan) {
                    final isBestValue = plan['name'] == 'Growth';
                    final price = _asNum(plan['price_ugx']);
                    final rate = _asNum(plan['rate_ugx']);
                    
                    return Card(
                      margin: const EdgeInsets.only(bottom: 16),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(16),
                        side: BorderSide(
                          color: isBestValue ? RomanSmsTheme.primaryGreen : const Color(0xFFE2E8F0),
                          width: isBestValue ? 2 : 1,
                        ),
                      ),
                      child: Padding(
                        padding: const EdgeInsets.all(20),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Text(
                                  plan['name'],
                                  style: GoogleFonts.inter(fontSize: 20, fontWeight: FontWeight.bold, color: RomanSmsTheme.textDark),
                                ),
                                if (isBestValue)
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                    decoration: BoxDecoration(color: RomanSmsTheme.primaryGreen, borderRadius: BorderRadius.circular(8)),
                                    child: Text('RECOMMENDED', style: GoogleFonts.inter(fontSize: 10, color: Colors.white, fontWeight: FontWeight.bold)),
                                  ),
                              ],
                            ),
                            const SizedBox(height: 8),
                            Row(
                              crossAxisAlignment: CrossAxisAlignment.end,
                              children: [
                                Text(
                                  currencyFormat.format(price),
                                  style: GoogleFonts.inter(fontSize: 24, fontWeight: FontWeight.bold, color: RomanSmsTheme.textDark),
                                ),
                                const SizedBox(width: 8),
                                Padding(
                                  padding: const EdgeInsets.only(bottom: 4),
                                  child: Text(
                                    'for ${plan['credits']} SMS',
                                    style: GoogleFonts.inter(fontSize: 14, color: RomanSmsTheme.textMuted),
                                  ),
                                ),
                              ],
                            ),
                            const Divider(height: 24),
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Text(
                                  '${currencyFormat.format(rate)} / SMS',
                                  style: GoogleFonts.inter(fontSize: 14, color: RomanSmsTheme.textMuted, fontWeight: FontWeight.w500),
                                ),
                                ElevatedButton(
                                  onPressed: _isProcessing ? null : () => _buyPlan(plan['id'], plan['name']),
                                  style: ElevatedButton.styleFrom(
                                    backgroundColor: isBestValue ? RomanSmsTheme.primaryGreen : RomanSmsTheme.textDark,
                                    foregroundColor: Colors.white,
                                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                                  ),
                                  child: const Text('Buy Plan'),
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
                    );
                  }).toList(),
                );
              },
            ),
            const SizedBox(height: 24),
            Center(
              child: Text(
                'Need a custom volume? Contact support.',
                style: GoogleFonts.inter(fontSize: 12, color: RomanSmsTheme.textMuted),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

