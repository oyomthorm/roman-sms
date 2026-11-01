import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';
import '../api/client.dart';
import '../theme/app_theme.dart';
import '../state/providers.dart';

class AddContactSheet extends ConsumerStatefulWidget {
  final int? initialGroupId;

  const AddContactSheet({super.key, this.initialGroupId});

  @override
  ConsumerState<AddContactSheet> createState() => _AddContactSheetState();
}

class _AddContactSheetState extends ConsumerState<AddContactSheet> {
  final _nameController = TextEditingController();
  final _phoneController = TextEditingController();
  bool _isSubmitting = false;
  int? _selectedGroupId;

  @override
  void initState() {
    super.initState();
    _selectedGroupId = widget.initialGroupId;
  }

  Future<void> _submit() async {
    if (_phoneController.text.isEmpty) return;
    if (_selectedGroupId == null) return;
    setState(() => _isSubmitting = true);
    try {
      await ApiClient.instance.dio.post('/api/v1/contacts', data: {
        'name': _nameController.text.trim(),
        'phone': _phoneController.text.trim(),
        'group_id': _selectedGroupId,
      });
      ref.invalidate(contactsProvider);
      if (mounted) Navigator.pop(context);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Failed to add contact. Ensure phone is valid (e.g., 0700123456) and a group is selected.')),
        );
      }
    } finally {
      if (mounted) setState(() => _isSubmitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final groupsAsync = ref.watch(groupsProvider);
    final canSubmit = !_isSubmitting
        && _selectedGroupId != null
        && groupsAsync.hasValue;

    return Padding(
      padding: EdgeInsets.only(
        bottom: MediaQuery.of(context).viewInsets.bottom,
        left: 20, right: 20, top: 20,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text('Add New Contact', style: GoogleFonts.inter(fontSize: 20, fontWeight: FontWeight.bold)),
          const SizedBox(height: 16),
          TextField(
            controller: _nameController,
            decoration: const InputDecoration(labelText: 'Full Name (Optional)', border: OutlineInputBorder()),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _phoneController,
            decoration: const InputDecoration(labelText: 'Phone Number (e.g. 0700123456)', border: OutlineInputBorder()),
            keyboardType: TextInputType.phone,
          ),
          const SizedBox(height: 12),
          groupsAsync.when(
            loading: () => const Padding(
              padding: EdgeInsets.symmetric(vertical: 16),
              child: Center(child: CircularProgressIndicator()),
            ),
            error: (e, _) => Padding(
              padding: const EdgeInsets.symmetric(vertical: 8),
              child: Text('Error loading groups: $e',
                  style: const TextStyle(color: Colors.red)),
            ),
            data: (groups) {
              if (groups.isEmpty) {
                return Padding(
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  child: Text(
                    'No groups exist yet. Create a group first.',
                    style: GoogleFonts.inter(color: Colors.orange),
                  ),
                );
              }
              return DropdownButtonFormField<int>(
                initialValue: _selectedGroupId,
                decoration: const InputDecoration(
                  labelText: 'Group (required)',
                  border: OutlineInputBorder(),
                ),
                items: [
                  for (final g in groups)
                    DropdownMenuItem<int>(
                      value: g['id'] as int,
                      child: Text(g['name'] as String? ?? 'Group #${g['id']}'),
                    ),
                ],
                onChanged: (v) => setState(() => _selectedGroupId = v),
              );
            },
          ),
          const SizedBox(height: 24),
          ElevatedButton(
            onPressed: canSubmit ? _submit : null,
            style: ElevatedButton.styleFrom(
              backgroundColor: RomanSmsTheme.primaryGreen,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(vertical: 16),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            ),
            child: _isSubmitting ? const CircularProgressIndicator(color: Colors.white) : const Text('Save Contact'),
          ),
          const SizedBox(height: 20),
        ],
      ),
    );
  }
}