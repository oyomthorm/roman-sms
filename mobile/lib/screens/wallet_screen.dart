import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:intl/intl.dart';
import '../theme/app_theme.dart';
import '../state/providers.dart';

class WalletScreen extends ConsumerWidget {
  const WalletScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final walletAsync = ref.watch(walletProvider);
    final txAsync = ref.watch(transactionsProvider);
    final currencyFormat = NumberFormat.currency(locale: 'en_UG', symbol: 'UGX ', decimalDigits: 0);

    return Scaffold(
      appBar: AppBar(
        title: Text('Wallet & Ledger', style: GoogleFonts.inter(fontWeight: FontWeight.bold)),
        backgroundColor: Colors.transparent,
        elevation: 0,
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(walletProvider);
          ref.invalidate(transactionsProvider);
        },
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // 1. Balance Hero Card
              walletAsync.when(
                loading: () => const Center(child: CircularProgressIndicator()),
                error: (e, _) => Text('Error loading wallet: $e'),
                data: (wallet) => Container(
                  padding: const EdgeInsets.all(24),
                  decoration: BoxDecoration(
                    color: RomanSmsTheme.lightGreen,
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text("Available Balance", style: GoogleFonts.inter(fontSize: 14, fontWeight: FontWeight.w500, color: RomanSmsTheme.primaryGreen)),
                      const SizedBox(height: 8),
                      Text(currencyFormat.format(wallet['value_ugx']), style: GoogleFonts.inter(fontSize: 36, fontWeight: FontWeight.bold, color: RomanSmsTheme.textDark)),
                      const SizedBox(height: 4),
                      Text("${wallet['balance']} SMS remaining", style: GoogleFonts.inter(fontSize: 14, color: RomanSmsTheme.textMuted)),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 24),

              // 2. Transaction History (Matches mockup style)
              Text('Transaction History', style: GoogleFonts.inter(fontSize: 18, fontWeight: FontWeight.bold)),
              const SizedBox(height: 12),
              
              txAsync.when(
                loading: () => const Center(child: CircularProgressIndicator()),
                error: (e, _) => Center(child: Text('Error loading transactions: $e')),
                data: (transactions) {
                  if (transactions.isEmpty) {
                    return Center(child: Text('No transactions yet.', style: GoogleFonts.inter(color: RomanSmsTheme.textMuted)));
                  }
                  
                  return Card(
                    child: Column(
                      children: transactions.asMap().entries.map((entry) {
                        final index = entry.key;
                        final tx = entry.value;
                        final delta = tx['delta'] as int;
                        final isCredit = delta > 0;

                        return Column(
                          children: [
                            ListTile(
                              leading: CircleAvatar(
                                backgroundColor: isCredit ? RomanSmsTheme.lightGreen : const Color(0xFFFFEBEE),
                                child: Icon(
                                  isCredit ? Icons.add : Icons.send,
                                  color: isCredit ? RomanSmsTheme.primaryGreen : Colors.red,
                                  size: 20,
                                ),
                              ),
                              title: Text(
                                tx['reason'].toString().replaceAll('_', ' ').toUpperCase(),
                                style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13),
                              ),
                              subtitle: Text(
                                DateFormat('MMM dd, yyyy • hh:mm a').format(DateTime.parse(tx['created_at'])),
                                style: GoogleFonts.inter(fontSize: 11),
                              ),
                              trailing: Column(
                                mainAxisAlignment: MainAxisAlignment.center,
                                crossAxisAlignment: CrossAxisAlignment.end,
                                children: [
                                  Text(
                                    '${isCredit ? '+' : ''}${delta} SMS',
                                    style: GoogleFonts.inter(
                                      fontWeight: FontWeight.bold,
                                      fontSize: 14,
                                      color: isCredit ? RomanSmsTheme.primaryGreen : Colors.red,
                                    ),
                                  ),
                                  Text(
                                    'Bal: ${tx['balance_after']}',
                                    style: GoogleFonts.inter(fontSize: 10, color: RomanSmsTheme.textMuted),
                                  ),
                                ],
                              ),
                            ),
                            if (index < transactions.length - 1) const Divider(height: 1, indent: 60),
                          ],
                        );
                      }).toList(),
                    ),
                  );
                },
              ),
            ],
          ),
        ),
      ),
    );
  }
}
