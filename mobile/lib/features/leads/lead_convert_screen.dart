import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/di/providers.dart';
import '../common/date_field.dart';
import '../common/form_section.dart';
import '../common/select_list_screen.dart';

class LeadConvertScreen extends ConsumerStatefulWidget {
  const LeadConvertScreen({super.key, required this.lead});

  final Map<String, dynamic> lead;

  @override
  ConsumerState<LeadConvertScreen> createState() => _LeadConvertScreenState();
}

class _LeadConvertScreenState extends ConsumerState<LeadConvertScreen> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _nameController;
  late final TextEditingController _codeController;
  late final TextEditingController _locationController;
  late final TextEditingController _builtUpController;
  late final TextEditingController _startDateController;
  late final TextEditingController _handoverController;
  late final TextEditingController _descriptionController;

  String _projectType = 'residential';
  String _health = 'on_track';
  String _stage = 'Enquiry';
  int? _managerId;
  int? _engineerId;
  String _managerLabel = '';
  String _engineerLabel = '';
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _nameController = TextEditingController(
      text: widget.lead['title']?.toString() ?? '',
    );
    _codeController = TextEditingController();
    _locationController = TextEditingController();
    _builtUpController = TextEditingController();
    _startDateController = TextEditingController();
    _handoverController = TextEditingController();
    _descriptionController = TextEditingController(
      text: widget.lead['planning_details']?.toString() ?? '',
    );
  }

  @override
  void dispose() {
    _nameController.dispose();
    _codeController.dispose();
    _locationController.dispose();
    _builtUpController.dispose();
    _startDateController.dispose();
    _handoverController.dispose();
    _descriptionController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Convert Lead')),
      body: SafeArea(
        child: Form(
          key: _formKey,
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              FormSection(
                title: 'Project Details',
                children: [
                  TextFormField(
                    controller: _nameController,
                    decoration: const InputDecoration(
                      labelText: 'Project Name *',
                    ),
                    validator: (value) {
                      if (value == null || value.trim().isEmpty) {
                        return 'Project name is required.';
                      }
                      return null;
                    },
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _codeController,
                    decoration: const InputDecoration(
                      labelText: 'Project Code *',
                    ),
                    validator: (value) {
                      if (value == null || value.trim().isEmpty) {
                        return 'Project code is required.';
                      }
                      return null;
                    },
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    initialValue: _projectType,
                    decoration: const InputDecoration(
                      labelText: 'Project Type',
                    ),
                    items: const [
                      DropdownMenuItem(
                        value: 'residential',
                        child: Text('Residential'),
                      ),
                      DropdownMenuItem(
                        value: 'commercial',
                        child: Text('Commercial'),
                      ),
                      DropdownMenuItem(value: 'other', child: Text('Other')),
                    ],
                    onChanged: (value) =>
                        setState(() => _projectType = value ?? _projectType),
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _locationController,
                    decoration: const InputDecoration(labelText: 'Location'),
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _builtUpController,
                    decoration: const InputDecoration(
                      labelText: 'Built-up Area',
                    ),
                    keyboardType: TextInputType.number,
                  ),
                  const SizedBox(height: 12),
                  DateField(
                    controller: _startDateController,
                    label: 'Start Date',
                  ),
                  const SizedBox(height: 12),
                  DateField(
                    controller: _handoverController,
                    label: 'Expected Handover',
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    initialValue: _stage,
                    decoration: const InputDecoration(labelText: 'Stage'),
                    items: const [
                      DropdownMenuItem(
                        value: 'Enquiry',
                        child: Text('Enquiry'),
                      ),
                      DropdownMenuItem(
                        value: 'Concept',
                        child: Text('Concept'),
                      ),
                      DropdownMenuItem(
                        value: 'Design Development',
                        child: Text('Design Development'),
                      ),
                      DropdownMenuItem(
                        value: 'Approvals',
                        child: Text('Approvals'),
                      ),
                      DropdownMenuItem(
                        value: 'Working Drawings',
                        child: Text('Working Drawings'),
                      ),
                      DropdownMenuItem(
                        value: 'Site Execution',
                        child: Text('Site Execution'),
                      ),
                      DropdownMenuItem(
                        value: 'Handover',
                        child: Text('Handover'),
                      ),
                      DropdownMenuItem(value: 'Closed', child: Text('Closed')),
                    ],
                    onChanged: (value) =>
                        setState(() => _stage = value ?? _stage),
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    initialValue: _health,
                    decoration: const InputDecoration(
                      labelText: 'Health Status',
                    ),
                    items: const [
                      DropdownMenuItem(
                        value: 'on_track',
                        child: Text('On Track'),
                      ),
                      DropdownMenuItem(
                        value: 'at_risk',
                        child: Text('At Risk'),
                      ),
                      DropdownMenuItem(
                        value: 'delayed',
                        child: Text('Delayed'),
                      ),
                    ],
                    onChanged: (value) =>
                        setState(() => _health = value ?? _health),
                  ),
                  const SizedBox(height: 12),
                  _SelectRow(
                    label: 'Project Manager',
                    value: _managerLabel.isEmpty
                        ? 'Select manager'
                        : _managerLabel,
                    onTap: () async {
                      final selected = await Navigator.of(context)
                          .push<SelectOption>(
                            MaterialPageRoute(
                              builder: (_) => const SelectListScreen(
                                title: 'Select Manager',
                                endpoint: 'users',
                              ),
                            ),
                          );
                      if (selected != null) {
                        setState(() {
                          _managerId = selected.id;
                          _managerLabel = selected.label;
                        });
                      }
                    },
                  ),
                  const SizedBox(height: 12),
                  _SelectRow(
                    label: 'Site Engineer',
                    value: _engineerLabel.isEmpty
                        ? 'Select engineer'
                        : _engineerLabel,
                    onTap: () async {
                      final selected = await Navigator.of(context)
                          .push<SelectOption>(
                            MaterialPageRoute(
                              builder: (_) => const SelectListScreen(
                                title: 'Select Engineer',
                                endpoint: 'users',
                              ),
                            ),
                          );
                      if (selected != null) {
                        setState(() {
                          _engineerId = selected.id;
                          _engineerLabel = selected.label;
                        });
                      }
                    },
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _descriptionController,
                    decoration: const InputDecoration(labelText: 'Description'),
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
                          final payload = {
                            'project': {
                              'name': _nameController.text.trim(),
                              'code': _codeController.text.trim(),
                              'project_type': _projectType,
                              'location': _locationController.text.trim(),
                              'built_up_area':
                                  double.tryParse(
                                    _builtUpController.text.trim(),
                                  ) ??
                                  0,
                              'start_date':
                                  _startDateController.text.trim().isEmpty
                                  ? null
                                  : _startDateController.text.trim(),
                              'expected_handover':
                                  _handoverController.text.trim().isEmpty
                                  ? null
                                  : _handoverController.text.trim(),
                              'current_stage': _stage,
                              'health_status': _health,
                              'project_manager': _managerId,
                              'site_engineer': _engineerId,
                              'description': _descriptionController.text.trim(),
                            },
                          };
                          final repo = ref.read(apiRepositoryProvider);
                          final response = await repo.post(
                            'leads/${widget.lead['id']}/convert/',
                            payload,
                          );
                          if (!context.mounted) {
                            return;
                          }
                          final data =
                              response.data as Map<String, dynamic>? ?? {};
                          Navigator.of(context).pop(data);
                        } catch (error) {
                          if (!context.mounted) {
                            return;
                          }
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(
                              content: Text('Failed to convert lead: $error'),
                            ),
                          );
                        } finally {
                          if (mounted) {
                            setState(() => _saving = false);
                          }
                        }
                      },
                child: Text(_saving ? 'Converting...' : 'Convert Lead'),
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
