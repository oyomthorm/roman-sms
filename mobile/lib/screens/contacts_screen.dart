import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';
import '../theme/app_theme.dart';
import '../state/providers.dart';
import '../widgets/add_contact_sheet.dart';

class ContactsScreen extends ConsumerWidget {
  const ContactsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final contactsAsync = ref.watch(contactsProvider);

    return Scaffold(
      appBar: AppBar(
        title: Text('Contacts', style: GoogleFonts.inter(fontWeight: FontWeight.bold)),
        backgroundColor: Colors.transparent,
        elevation: 0,
        actions: [
          IconButton(
            icon: const Icon(Icons.search),
            onPressed: () {
              // TODO: Implement Search
            },
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () {
          showModalBottomSheet(context: context, isScrollControlled: true, builder: (context) => const AddContactSheet());
        },
        backgroundColor: RomanSmsTheme.primaryGreen,
        icon: const Icon(Icons.person_add, color: Colors.white),
        label: Text('Add Contact', style: GoogleFonts.inter(color: Colors.white, fontWeight: FontWeight.bold)),
      ),
      body: RefreshIndicator(
        onRefresh: () async => ref.invalidate(contactsProvider),
        child: contactsAsync.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => Center(child: Text('Error loading contacts: $e')),
          data: (contacts) {
            // Calculate stats for the top circles
            final totalContacts = contacts.length;
            final optedOut = contacts.where((c) => c['opted_out'] == true).length;
            final groups = contacts.map((c) => c['group_id']).where((id) => id != null).toSet().length;

            return ListView(
              padding: const EdgeInsets.all(20),
              children: [
                // Top Stats (Adapted from Image 4 - Shares Overview circles)
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    _buildCircleStat('Total', totalContacts.toString()),
                    _buildCircleStat('Groups', groups.toString()),
                    _buildCircleStat('Opt-outs', optedOut.toString(), isWarning: true),
                  ],
                ),
                const SizedBox(height: 24),
                Text('All Contacts', style: GoogleFonts.inter(fontSize: 18, fontWeight: FontWeight.bold)),
                const SizedBox(height: 12),
                
                if (contacts.isEmpty)
                  Center(
                    child: Padding(
                      padding: const EdgeInsets.all(32.0),
                      child: Text('No contacts yet. Add one to get started!', style: GoogleFonts.inter(color: RomanSmsTheme.textMuted)),
                    ),
                  )
                else
                  Card(
                    child: Column(
                      children: contacts.asMap().entries.map((entry) {
                        final index = entry.key;
                        final contact = entry.value;
                        final isOptedOut = contact['opted_out'] == true;

                        return Column(
                          children: [
                            ListTile(
                              leading: CircleAvatar(
                                backgroundColor: isOptedOut ? Colors.grey.shade200 : RomanSmsTheme.lightGreen,
                                child: Icon(
                                  Icons.person, 
                                  color: isOptedOut ? Colors.grey : RomanSmsTheme.primaryGreen
                                ),
                              ),
                              title: Text(
                                contact['name'] ?? 'Unknown Name',
                                style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 14),
                              ),
                              subtitle: Text(contact['phone'], style: GoogleFonts.inter(fontSize: 12)),
                              trailing: isOptedOut
                                  ? Container(
                                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                      decoration: BoxDecoration(
                                        color: Colors.red.shade50,
                                        borderRadius: BorderRadius.circular(8),
                                      ),
                                      child: Text('Opted Out', style: GoogleFonts.inter(fontSize: 10, color: Colors.red, fontWeight: FontWeight.bold)),
                                    )
                                  : const Icon(Icons.chevron_right, color: Colors.grey),
                            ),
                            if (index < contacts.length - 1) const Divider(height: 1, indent: 60),
                          ],
                        );
                      }).toList(),
                    ),
                  ),
                const SizedBox(height: 80), // Space for FAB
              ],
            );
          },
        ),
      ),
    );
  }

  Widget _buildCircleStat(String label, String value, {bool isWarning = false}) {
    return Column(
      children: [
        Container(
          width: 100,
          height: 100,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: Colors.white,
            border: Border.all(
              color: isWarning ? Colors.red.shade100 : RomanSmsTheme.lightGreen,
              width: 4,
            ),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(0.02),
                blurRadius: 10,
                offset: const Offset(0, 4),
              ),
            ],
          ),
          child: Center(
            child: Text(
              value,
              style: GoogleFonts.inter(
                fontSize: 24,
                fontWeight: FontWeight.bold,
                color: isWarning ? Colors.red : RomanSmsTheme.primaryGreen,
              ),
            ),
          ),
        ),
        const SizedBox(height: 8),
        Text(label, style: GoogleFonts.inter(fontSize: 12, color: RomanSmsTheme.textMuted, fontWeight: FontWeight.w600)),
      ],
    );
  }
}

