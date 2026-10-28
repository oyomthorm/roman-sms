import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';
import '../theme/app_theme.dart';
import '../state/providers.dart';

class CampaignDetailScreen extends ConsumerWidget {
  final int campaignId;
  const CampaignDetailScreen({super.key, required this.campaignId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final detailAsync = ref.watch(campaignDetailProvider(campaignId));

    return Scaffold(
      appBar: AppBar(title: Text('Campaign Report', style: GoogleFonts.inter(fontWeight: FontWeight.bold))),
      body: detailAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(child: Text('Error: $e')),
        data: (data) {
          final breakdown = data['breakdown'] as Map<String, dynamic>? ?? {};
          
          return ListView(
            padding: const EdgeInsets.all(20),
            children: [
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    children: [
                      Text(data['name'] ?? 'Campaign', style: GoogleFonts.inter(fontSize: 20, fontWeight: FontWeight.bold)),
                      const SizedBox(height: 8),
                      Text('Status: ${data['status']?.toUpperCase()}', style: GoogleFonts.inter(color: RomanSmsTheme.primaryGreen, fontWeight: FontWeight.bold)),
                      const Divider(height: 32),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceAround,
                        children: [
                          _buildStat('Total', '${data['recipient_count'] ?? 0}'),
                          _buildStat('Cost', '${data['cost_credits'] ?? 0} SMS'),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 24),
              Text('Delivery Breakdown', style: GoogleFonts.inter(fontSize: 18, fontWeight: FontWeight.bold)),
              const SizedBox(height: 12),
              if (breakdown.isEmpty)
                Text('No messages processed yet.', style: GoogleFonts.inter(color: RomanSmsTheme.textMuted))
              else
                Card(
                  child: Column(
                    children: breakdown.entries.map((e) {
                      final isDelivered = e.key == 'delivered';
                      final isFailed = e.key == 'failed' || e.key == 'delivery_failed';
                      return ListTile(
                        leading: Icon(
                          isDelivered ? Icons.check_circle : isFailed ? Icons.error : Icons.hourglass_empty,
                          color: isDelivered ? RomanSmsTheme.primaryGreen : isFailed ? Colors.red : Colors.orange,
                        ),
                        title: Text(e.key.toUpperCase(), style: GoogleFonts.inter(fontWeight: FontWeight.w600)),
                        trailing: Text('${e.value}', style: GoogleFonts.inter(fontWeight: FontWeight.bold, fontSize: 16)),
                      );
                    }).toList(),
                  ),
                ),
            ],
          );
        },
      ),
    );
  }

  Widget _buildStat(String label, String value) {
    return Column(
      children: [
        Text(value, style: GoogleFonts.inter(fontSize: 20, fontWeight: FontWeight.bold, color: RomanSmsTheme.textDark)),
        Text(label, style: GoogleFonts.inter(fontSize: 12, color: RomanSmsTheme.textMuted)),
      ],
    );
  }
}
