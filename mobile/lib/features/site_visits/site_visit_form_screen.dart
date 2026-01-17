import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/di/providers.dart';
import '../common/date_field.dart';
import '../common/form_section.dart';
import '../common/select_list_screen.dart';

class SiteVisitFormScreen extends ConsumerStatefulWidget {
  const SiteVisitFormScreen({super.key, this.visit});

  final Map<String, dynamic>? visit;

  @override
  ConsumerState<SiteVisitFormScreen> createState() =>
      _SiteVisitFormScreenState();
}

class _SiteVisitFormScreenState extends ConsumerState<SiteVisitFormScreen> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _visitDateController;
  late final TextEditingController _locationController;
  late final TextEditingController _notesController;
  late final TextEditingController _expensesController;

  int? _projectId;
  String _projectLabel = '';
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    final visit = widget.visit ?? {};
    _visitDateController = TextEditingController(
      text: visit['visit_date']?.toString() ?? '',
    );
    _locationController = TextEditingController(
      text: visit['location']?.toString() ?? '',
    );
    _notesController = TextEditingController(
      text: visit['notes']?.toString() ?? '',
    );
    _expensesController = TextEditingController(
      text: visit['expenses']?.toString() ?? '',
    );
    _projectId = visit['project'] as int?;
    _projectLabel = visit['project_detail']?['name']?.toString() ?? '';
  }

  @override
  void dispose() {
    _visitDateController.dispose();
    _locationController.dispose();
    _notesController.dispose();
    _expensesController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isEdit = widget.visit != null;
    return Scaffold(
      appBar: AppBar(
        title: Text(isEdit ? 'Edit Site Visit' : 'New Site Visit'),
      ),
      body: SafeArea(
        child: Form(
          key: _formKey,
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              FormSection(
                title: 'Visit Details',
                children: [
                  _SelectRow(
                    label: 'Project *',
                    value: _projectLabel.isEmpty
                        ? 'Select project'
                        : _projectLabel,
                    onTap: () async {
                      final selected = await Navigator.of(context)
                          .push<SelectOption>(
                            MaterialPageRoute(
                              builder: (_) => const SelectListScreen(
                                title: 'Select Project',
                                endpoint: 'projects',
                              ),
                            ),
                          );
                      if (selected != null) {
                        setState(() {
                          _projectId = selected.id;
                          _projectLabel = selected.label;
                        });
                      }
                    },
                  ),
                  const SizedBox(height: 12),
                  DateField(
                    controller: _visitDateController,
                    label: 'Visit Date *',
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _locationController,
                    decoration: const InputDecoration(labelText: 'Location'),
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _expensesController,
                    decoration: const InputDecoration(labelText: 'Expenses'),
                    keyboardType: TextInputType.number,
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
                        if (_projectId == null) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(content: Text('Select a project.')),
                          );
                          return;
                        }
                        if (_visitDateController.text.trim().isEmpty) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                              content: Text('Visit date is required.'),
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
                            'project': _projectId,
                            'visit_date': _visitDateController.text.trim(),
                            'location': _locationController.text.trim(),
                            'expenses':
                                double.tryParse(
                                  _expensesController.text.trim(),
                                ) ??
                                0,
                            'notes': _notesController.text.trim(),
                          };
                          final repo = ref.read(apiRepositoryProvider);
                          Map<String, dynamic> saved;
                          if (isEdit) {
                            saved = await repo.update(
                              'site-visits',
                              widget.visit!['id'] as int,
                              payload,
                            );
                          } else {
                            saved = await repo.create('site-visits', payload);
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
                              content: Text(
                                'Failed to save site visit: $error',
                              ),
                            ),
                          );
                        } finally {
                          if (mounted) {
                            setState(() => _saving = false);
                          }
                        }
                      },
                child: Text(_saving ? 'Saving...' : 'Save Site Visit'),
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
