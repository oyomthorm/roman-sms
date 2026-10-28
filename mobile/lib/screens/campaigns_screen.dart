import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:intl/intl.dart';
import '../theme/app_theme.dart';
import '../state/providers.dart';

class CampaignsScreen extends ConsumerWidget {
  const CampaignsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final campaignsAsync = ref.watch(campaignsProvider);

    return Scaffold(
      appBar: AppBar(
        title: Text('Campaigns', style: GoogleFonts.inter(fontWeight: FontWeight.bold)),
        backgroundColor: Colors.transparent,
        elevation: 0,
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => context.push('/campaigns/new'),
        backgroundColor: RomanSmsTheme.primaryGreen,
        icon: const Icon(Icons.add, color: Colors.white),
        label: Text('New', style: GoogleFonts.inter(color: Colors.white, fontWeight: FontWeight.bold)),
      ),
      body: RefreshIndicator(
        onRefresh: () async => ref.invalidate(campaignsProvider),
        child: campaignsAsync.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => Center(child: Text('Error loading campaigns: $e')),
          data: (campaigns) {
            if (campaigns.isEmpty) {
              return Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.campaign_outlined, size: 64, color: Colors.grey),
                    const SizedBox(height: 16),
                    Text('No campaigns yet.', style: GoogleFonts.inter(fontSize: 16, color: RomanSmsTheme.textMuted)),
                  ],
                ),
              );
            }

            return ListView.builder(
              padding: const EdgeInsets.all(20),
              itemCount: campaigns.length,
              itemBuilder: (context, index) {
                final c = campaigns[index];
                final status = c['status'] ?? 'unknown';
                final isComplete = status == 'complete' || status == 'sent';
                
                return Card(
                  margin: const EdgeInsets.only(bottom: 12),
                  child: ListTile(
                    contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                    onTap: () => context.push('/campaigns/${c['id']}'),
                    title: Text(
                      c['name'] ?? 'Untitled Campaign',
                      style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 15),
                    ),
                    subtitle: Padding(
                      padding: const EdgeInsets.only(top: 4),
                      child: Text(
                        DateFormat('MMM dd, yyyy • HH:mm').format(DateTime.parse(c['created_at'])),
                        style: GoogleFonts.inter(fontSize: 12),
                      ),
                    ),
                    trailing: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                          decoration: BoxDecoration(
                            color: isComplete ? RomanSmsTheme.lightGreen : Colors.orange.shade50,
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Text(
                            status.toUpperCase(),
                            style: GoogleFonts.inter(
                              fontSize: 10, 
                              fontWeight: FontWeight.bold,
                              color: isComplete ? RomanSmsTheme.primaryGreen : Colors.orange,
                            ),
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text('${c['recipient_count'] ?? 0} recipients', style: GoogleFonts.inter(fontSize: 11, color: RomanSmsTheme.textMuted)),
                      ],
                    ),
                  ),
                );
              },
            );
          },
        ),
      ),
    );
  }
}
