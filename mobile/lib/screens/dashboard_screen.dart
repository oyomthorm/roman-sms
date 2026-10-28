import 'package:go_router/go_router.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:intl/intl.dart';
import '../theme/app_theme.dart';
import '../state/providers.dart';

class DashboardScreen extends ConsumerWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final walletAsync = ref.watch(walletProvider);
    final statsAsync = ref.watch(dashboardStatsProvider);
    final currencyFormat = NumberFormat.currency(locale: 'en_UG', symbol: 'UGX ', decimalDigits: 0);

    return Scaffold(
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: () async {
            ref.invalidate(walletProvider);
            ref.invalidate(dashboardStatsProvider);
          },
          child: SingleChildScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.all(20.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Header
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Row(
                      children: [
                        CircleAvatar(
                          radius: 24,
                          backgroundColor: RomanSmsTheme.lightGreen,
                          child: const Icon(Icons.person, color: RomanSmsTheme.primaryGreen, size: 30),
                        ),
                        const SizedBox(width: 12),
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text("Hello, Admin", style: GoogleFonts.inter(fontSize: 20, fontWeight: FontWeight.bold, color: RomanSmsTheme.textDark)),
                            Text("Roman SMS â€¢ Verified", style: GoogleFonts.inter(fontSize: 12, color: RomanSmsTheme.textMuted)),
                          ],
                        ),
                      ],
                    ),
                    IconButton(
                      icon: const Icon(Icons.notifications_none, color: RomanSmsTheme.textDark, size: 28),
                      onPressed: () {},
                    ),
                  ],
                ),
                const SizedBox(height: 24),

                // Wallet Card (Live)
                walletAsync.when(
                  loading: () => const Center(child: CircularProgressIndicator()),
                  error: (e, _) => Text("Error loading wallet: $e"),
                  data: (wallet) {
                    final balanceUgx = wallet['value_ugx'] ?? 0;
                    final smsCount = wallet['balance'] ?? 0;
                    
                    return Container(
                      padding: const EdgeInsets.all(24),
                      decoration: BoxDecoration(
                        color: RomanSmsTheme.lightGreen,
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text("Total Wallet Value", style: GoogleFonts.inter(fontSize: 14, fontWeight: FontWeight.w500, color: RomanSmsTheme.primaryGreen)),
                          const SizedBox(height: 8),
                          Text(currencyFormat.format(balanceUgx), style: GoogleFonts.inter(fontSize: 32, fontWeight: FontWeight.bold, color: RomanSmsTheme.textDark)),
                          Text("Approx. $smsCount SMS", style: GoogleFonts.inter(fontSize: 14, color: RomanSmsTheme.textMuted)),
                          const SizedBox(height: 20),
                          Row(
                            children: [
                              Expanded(
                                child: ElevatedButton.icon(
                                  onPressed: () {}, // Navigate to Plans
                                  icon: const Icon(Icons.add_circle_outline, size: 20),
                                  label: const Text("Buy SMS"),
                                  style: ElevatedButton.styleFrom(
                                    backgroundColor: Colors.white,
                                    foregroundColor: RomanSmsTheme.textDark,
                                    elevation: 0,
                                    padding: const EdgeInsets.symmetric(vertical: 12),
                                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                                  ),
                                ),
                              ),
                              const SizedBox(width: 12),
                              Expanded(
                                child: ElevatedButton.icon(
                                  onPressed: () {}, // Navigate to Ledger
                                  icon: const Icon(Icons.receipt_long, size: 20),
                                  label: const Text("Ledger"),
                                  style: ElevatedButton.styleFrom(
                                    backgroundColor: Colors.transparent,
                                    foregroundColor: RomanSmsTheme.textDark,
                                    elevation: 0,
                                    padding: const EdgeInsets.symmetric(vertical: 12),
                                    side: const BorderSide(color: Colors.black12),
                                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                    );
                  },
                ),
                const SizedBox(height: 24),

                // Stats Overview
                statsAsync.when(
                  loading: () => const Center(child: CircularProgressIndicator()),
                  error: (e, _) => Text("Error loading stats: $e"),
                  data: (stats) => Column(
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text("Account Overview", style: GoogleFonts.inter(fontSize: 18, fontWeight: FontWeight.bold, color: RomanSmsTheme.textDark)),
                          Text("Details ->", style: GoogleFonts.inter(fontSize: 14, color: RomanSmsTheme.primaryGreen)),
                        ],
                      ),
                      const SizedBox(height: 12),
                      Row(
                        children: [
                          Expanded(child: _buildStatCard(Icons.send, "Sent (30d)", "${stats['sent_30d']} SMS")),
                          const SizedBox(width: 12),
                          Expanded(child: _buildStatCard(Icons.check_circle_outline, "Delivery Rate", stats['delivery_rate'].toString())),
                        ],
                      ),
                      const SizedBox(height: 24),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text("Recent Activity", style: GoogleFonts.inter(fontSize: 18, fontWeight: FontWeight.bold, color: RomanSmsTheme.textDark)),
                          Text("See all ->", style: GoogleFonts.inter(fontSize: 14, color: RomanSmsTheme.primaryGreen)),
                        ],
                      ),
                      const SizedBox(height: 12),
                      Card(
                        child: Column(
                          children: (stats['recent_activity'] as List).map((tx) {
                            final isCredit = tx['type'] == 'credit';
                            return Column(
                              children: [
                                ListTile(
                                  leading: CircleAvatar(
                                    backgroundColor: isCredit ? RomanSmsTheme.lightGreen : const Color(0xFFFFEBEE),
                                    child: Icon(isCredit ? Icons.add : Icons.send, color: isCredit ? RomanSmsTheme.primaryGreen : Colors.red, size: 20),
                                  ),
                                  title: Text(tx['title'], style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 14)),
                                  subtitle: Text(tx['date'], style: GoogleFonts.inter(fontSize: 12)),
                                  trailing: Text(
                                    tx['amount'],
                                    style: GoogleFonts.inter(fontWeight: FontWeight.bold, fontSize: 14, color: isCredit ? RomanSmsTheme.primaryGreen : Colors.red),
                                  ),
                                ),
                                if (tx != (stats['recent_activity'] as List).last) const Divider(height: 1, indent: 60),
                              ],
                            );
                          }).toList(),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildStatCard(IconData icon, String title, String value) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, color: RomanSmsTheme.primaryGreen),
            const SizedBox(height: 12),
            Text(title, style: GoogleFonts.inter(fontSize: 12, color: RomanSmsTheme.textMuted)),
            const SizedBox(height: 4),
            Text(value, style: GoogleFonts.inter(fontSize: 16, fontWeight: FontWeight.bold, color: RomanSmsTheme.textDark)),
          ],
        ),
      ),
    );
  }
}


