import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';
import '../api/client.dart';
import '../theme/app_theme.dart';
import '../state/providers.dart';

class AddContactSheet extends ConsumerStatefulWidget {
  const AddContactSheet({super.key});

  @override
  ConsumerState<AddContactSheet> createState() => _AddContactSheetState();
}

class _AddContactSheetState extends ConsumerState<AddContactSheet> {
  final _nameController = TextEditingController();
  final _phoneController = TextEditingController();
  bool _isSubmitting = false;

  Future<void> _submit() async {
    if (_phoneController.text.isEmpty) return;
    setState(() => _isSubmitting = true);
    try {
      await ApiClient.instance.dio.post('/api/v1/contacts', data: {
        'name': _nameController.text.trim(),
        'phone': _phoneController.text.trim(),
      });
      ref.invalidate(contactsProvider);
      if (mounted) Navigator.pop(context);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Failed to add contact. Ensure phone is valid (e.g., 0700123456).')),
        );
      }
    } finally {
      if (mounted) setState(() => _isSubmitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
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
          const SizedBox(height: 24),
          ElevatedButton(
            onPressed: _isSubmitting ? null : _submit,
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
