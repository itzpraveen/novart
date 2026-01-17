import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/di/providers.dart';
import '../common/form_section.dart';

class ClientFormScreen extends ConsumerStatefulWidget {
  const ClientFormScreen({super.key, this.client});

  final Map<String, dynamic>? client;

  @override
  ConsumerState<ClientFormScreen> createState() => _ClientFormScreenState();
}

class _ClientFormScreenState extends ConsumerState<ClientFormScreen> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _nameController;
  late final TextEditingController _phoneController;
  late final TextEditingController _emailController;
  late final TextEditingController _addressController;
  late final TextEditingController _cityController;
  late final TextEditingController _stateController;
  late final TextEditingController _postalController;
  late final TextEditingController _notesController;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    final client = widget.client ?? {};
    _nameController = TextEditingController(
      text: client['name']?.toString() ?? '',
    );
    _phoneController = TextEditingController(
      text: client['phone']?.toString() ?? '',
    );
    _emailController = TextEditingController(
      text: client['email']?.toString() ?? '',
    );
    _addressController = TextEditingController(
      text: client['address']?.toString() ?? '',
    );
    _cityController = TextEditingController(
      text: client['city']?.toString() ?? '',
    );
    _stateController = TextEditingController(
      text: client['state']?.toString() ?? '',
    );
    _postalController = TextEditingController(
      text: client['postal_code']?.toString() ?? '',
    );
    _notesController = TextEditingController(
      text: client['notes']?.toString() ?? '',
    );
  }

  @override
  void dispose() {
    _nameController.dispose();
    _phoneController.dispose();
    _emailController.dispose();
    _addressController.dispose();
    _cityController.dispose();
    _stateController.dispose();
    _postalController.dispose();
    _notesController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isEdit = widget.client != null;
    return Scaffold(
      appBar: AppBar(title: Text(isEdit ? 'Edit Client' : 'New Client')),
      body: SafeArea(
        child: Form(
          key: _formKey,
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              FormSection(
                title: 'Client Details',
                children: [
                  TextFormField(
                    controller: _nameController,
                    decoration: const InputDecoration(labelText: 'Name *'),
                    validator: (value) {
                      if (value == null || value.trim().isEmpty) {
                        return 'Client name is required.';
                      }
                      return null;
                    },
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _phoneController,
                    decoration: const InputDecoration(labelText: 'Phone'),
                    keyboardType: TextInputType.phone,
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _emailController,
                    decoration: const InputDecoration(labelText: 'Email'),
                    keyboardType: TextInputType.emailAddress,
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _addressController,
                    decoration: const InputDecoration(labelText: 'Address'),
                    maxLines: 2,
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _cityController,
                    decoration: const InputDecoration(labelText: 'City'),
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _stateController,
                    decoration: const InputDecoration(labelText: 'State'),
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _postalController,
                    decoration: const InputDecoration(labelText: 'Postal Code'),
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _notesController,
                    decoration: const InputDecoration(labelText: 'Notes'),
                    maxLines: 3,
                  ),
                ],
              ),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: _saving
                    ? null
                    : () async {
                        if (!_formKey.currentState!.validate()) {
                          return;
                        }
                        setState(() => _saving = true);
                        try {
                          final data = {
                            'name': _nameController.text.trim(),
                            'phone': _phoneController.text.trim(),
                            'email': _emailController.text.trim(),
                            'address': _addressController.text.trim(),
                            'city': _cityController.text.trim(),
                            'state': _stateController.text.trim(),
                            'postal_code': _postalController.text.trim(),
                            'notes': _notesController.text.trim(),
                          };
                          final repo = ref.read(apiRepositoryProvider);
                          Map<String, dynamic> saved;
                          if (isEdit) {
                            saved = await repo.update(
                              'clients',
                              widget.client!['id'] as int,
                              data,
                            );
                          } else {
                            saved = await repo.create('clients', data);
                          }
                          if (!context.mounted) {
                            return;
                          }
                          Navigator.of(context).pop(saved);
                        } catch (error) {
                          if (!context.mounted) {
                            return;
                          }
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(
                              content: Text('Failed to save client: $error'),
                            ),
                          );
                        } finally {
                          if (mounted) {
                            setState(() => _saving = false);
                          }
                        }
                      },
                child: Text(_saving ? 'Saving...' : 'Save Client'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
