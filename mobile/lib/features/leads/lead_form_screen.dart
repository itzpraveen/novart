import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/di/providers.dart';
import '../common/form_section.dart';
import '../common/select_list_screen.dart';

class LeadFormScreen extends ConsumerStatefulWidget {
  const LeadFormScreen({super.key, this.lead});

  final Map<String, dynamic>? lead;

  @override
  ConsumerState<LeadFormScreen> createState() => _LeadFormScreenState();
}

class _LeadFormScreenState extends ConsumerState<LeadFormScreen> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _titleController;
  late final TextEditingController _sourceController;
  late final TextEditingController _valueController;
  late final TextEditingController _notesController;
  late final TextEditingController _planningController;

  int? _clientId;
  String _clientLabel = '';
  String _status = 'new';
  bool _saving = false;

  static const statuses = ['new', 'discussion', 'won', 'lost'];

  @override
  void initState() {
    super.initState();
    final lead = widget.lead ?? {};
    _titleController = TextEditingController(
      text: lead['title']?.toString() ?? '',
    );
    _sourceController = TextEditingController(
      text: lead['lead_source']?.toString() ?? '',
    );
    _valueController = TextEditingController(
      text: lead['estimated_value']?.toString() ?? '',
    );
    _notesController = TextEditingController(
      text: lead['notes']?.toString() ?? '',
    );
    _planningController = TextEditingController(
      text: lead['planning_details']?.toString() ?? '',
    );
    _clientId = lead['client'] as int?;
    _status = lead['status']?.toString() ?? 'new';
    final clientDetail = lead['client_detail'] as Map<String, dynamic>?;
    _clientLabel = clientDetail?['name']?.toString() ?? '';
  }

  @override
  void dispose() {
    _titleController.dispose();
    _sourceController.dispose();
    _valueController.dispose();
    _notesController.dispose();
    _planningController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isEdit = widget.lead != null;

    return Scaffold(
      appBar: AppBar(title: Text(isEdit ? 'Edit Lead' : 'New Lead')),
      body: SafeArea(
        child: Form(
          key: _formKey,
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              FormSection(
                title: 'Lead Details',
                children: [
                  _SelectRow(
                    label: 'Client *',
                    value: _clientLabel.isEmpty
                        ? 'Select client'
                        : _clientLabel,
                    onTap: () async {
                      final selected = await Navigator.of(context)
                          .push<SelectOption>(
                            MaterialPageRoute(
                              builder: (_) => const SelectListScreen(
                                title: 'Select Client',
                                endpoint: 'clients',
                              ),
                            ),
                          );
                      if (selected != null) {
                        setState(() {
                          _clientId = selected.id;
                          _clientLabel = selected.label;
                        });
                      }
                    },
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _titleController,
                    decoration: const InputDecoration(labelText: 'Title *'),
                    validator: (value) {
                      if (value == null || value.trim().isEmpty) {
                        return 'Lead title is required.';
                      }
                      return null;
                    },
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    initialValue: _status,
                    decoration: const InputDecoration(labelText: 'Status'),
                    items: statuses
                        .map(
                          (status) => DropdownMenuItem(
                            value: status,
                            child: Text(
                              status.replaceAll('_', ' ').toUpperCase(),
                            ),
                          ),
                        )
                        .toList(),
                    onChanged: (value) {
                      if (value != null) {
                        setState(() => _status = value);
                      }
                    },
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _sourceController,
                    decoration: const InputDecoration(labelText: 'Lead Source'),
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _valueController,
                    decoration: const InputDecoration(
                      labelText: 'Estimated Value',
                    ),
                    keyboardType: TextInputType.number,
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _notesController,
                    decoration: const InputDecoration(labelText: 'Notes'),
                    maxLines: 3,
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _planningController,
                    decoration: const InputDecoration(
                      labelText: 'Planning Details',
                    ),
                    maxLines: 3,
                  ),
                ],
              ),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: _saving
                    ? null
                    : () async {
                        if (_clientId == null) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                              content: Text('Please select a client.'),
                            ),
                          );
                          return;
                        }
                        if (!_formKey.currentState!.validate()) {
                          return;
                        }
                        setState(() => _saving = true);
                        try {
                          final payload = {
                            'client': _clientId,
                            'title': _titleController.text.trim(),
                            'lead_source': _sourceController.text.trim(),
                            'status': _status,
                            'estimated_value':
                                _valueController.text.trim().isEmpty
                                ? 0
                                : double.tryParse(
                                        _valueController.text.trim(),
                                      ) ??
                                      0,
                            'notes': _notesController.text.trim(),
                            'planning_details': _planningController.text.trim(),
                          };
                          final repo = ref.read(apiRepositoryProvider);
                          Map<String, dynamic> saved;
                          if (isEdit) {
                            saved = await repo.update(
                              'leads',
                              widget.lead!['id'] as int,
                              payload,
                            );
                          } else {
                            saved = await repo.create('leads', payload);
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
                              content: Text('Failed to save lead: $error'),
                            ),
                          );
                        } finally {
                          if (mounted) {
                            setState(() => _saving = false);
                          }
                        }
                      },
                child: Text(_saving ? 'Saving...' : 'Save Lead'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SelectRow extends StatelessWidget {
  const _SelectRow({
    required this.label,
    required this.value,
    required this.onTap,
  });

  final String label;
  final String value;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      child: InputDecorator(
        decoration: InputDecoration(labelText: label),
        child: Row(
          children: [
            Expanded(child: Text(value)),
            const Icon(Icons.chevron_right),
          ],
        ),
      ),
    );
  }
}
