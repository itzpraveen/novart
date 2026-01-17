import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/di/providers.dart';
import '../common/date_field.dart';
import '../common/form_section.dart';
import '../common/select_list_screen.dart';

class TaskFormScreen extends ConsumerStatefulWidget {
  const TaskFormScreen({super.key, this.task});

  final Map<String, dynamic>? task;

  @override
  ConsumerState<TaskFormScreen> createState() => _TaskFormScreenState();
}

class _TaskFormScreenState extends ConsumerState<TaskFormScreen> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _titleController;
  late final TextEditingController _descriptionController;
  late final TextEditingController _dueDateController;
  late final TextEditingController _estimatedController;
  late final TextEditingController _actualController;
  late final TextEditingController _objectiveController;
  late final TextEditingController _outputController;
  late final TextEditingController _deliverablesController;
  late final TextEditingController _referencesController;
  late final TextEditingController _constraintsController;

  int? _projectId;
  int? _assigneeId;
  String _projectLabel = '';
  String _assigneeLabel = '';
  String _status = 'todo';
  String _priority = 'medium';
  bool _saving = false;

  static const statusOptions = ['todo', 'in_progress', 'done'];
  static const priorityOptions = ['low', 'medium', 'high'];

  @override
  void initState() {
    super.initState();
    final task = widget.task ?? {};
    _titleController = TextEditingController(
      text: task['title']?.toString() ?? '',
    );
    _descriptionController = TextEditingController(
      text: task['description']?.toString() ?? '',
    );
    _dueDateController = TextEditingController(
      text: task['due_date']?.toString() ?? '',
    );
    _estimatedController = TextEditingController(
      text: task['estimated_hours']?.toString() ?? '',
    );
    _actualController = TextEditingController(
      text: task['actual_hours']?.toString() ?? '',
    );
    _objectiveController = TextEditingController(
      text: task['objective']?.toString() ?? '',
    );
    _outputController = TextEditingController(
      text: task['expected_output']?.toString() ?? '',
    );
    _deliverablesController = TextEditingController(
      text: task['deliverables']?.toString() ?? '',
    );
    _referencesController = TextEditingController(
      text: task['references']?.toString() ?? '',
    );
    _constraintsController = TextEditingController(
      text: task['constraints']?.toString() ?? '',
    );

    _projectId = task['project'] as int?;
    _assigneeId = task['assigned_to'] as int?;
    _projectLabel = task['project_detail']?['name']?.toString() ?? '';
    _assigneeLabel = task['assigned_to_detail']?['full_name']?.toString() ?? '';
    _status = task['status']?.toString() ?? 'todo';
    _priority = task['priority']?.toString() ?? 'medium';
  }

  @override
  void dispose() {
    _titleController.dispose();
    _descriptionController.dispose();
    _dueDateController.dispose();
    _estimatedController.dispose();
    _actualController.dispose();
    _objectiveController.dispose();
    _outputController.dispose();
    _deliverablesController.dispose();
    _referencesController.dispose();
    _constraintsController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isEdit = widget.task != null;

    return Scaffold(
      appBar: AppBar(title: Text(isEdit ? 'Edit Task' : 'New Task')),
      body: SafeArea(
        child: Form(
          key: _formKey,
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              FormSection(
                title: 'Task Details',
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
                  TextFormField(
                    controller: _titleController,
                    decoration: const InputDecoration(labelText: 'Title *'),
                    validator: (value) {
                      if (value == null || value.trim().isEmpty) {
                        return 'Task title is required.';
                      }
                      return null;
                    },
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _descriptionController,
                    decoration: const InputDecoration(labelText: 'Description'),
                    maxLines: 3,
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    initialValue: _status,
                    decoration: const InputDecoration(labelText: 'Status'),
                    items: statusOptions
                        .map(
                          (status) => DropdownMenuItem(
                            value: status,
                            child: Text(
                              status.replaceAll('_', ' ').toUpperCase(),
                            ),
                          ),
                        )
                        .toList(),
                    onChanged: (value) =>
                        setState(() => _status = value ?? _status),
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    initialValue: _priority,
                    decoration: const InputDecoration(labelText: 'Priority'),
                    items: priorityOptions
                        .map(
                          (priority) => DropdownMenuItem(
                            value: priority,
                            child: Text(priority.toUpperCase()),
                          ),
                        )
                        .toList(),
                    onChanged: (value) =>
                        setState(() => _priority = value ?? _priority),
                  ),
                  const SizedBox(height: 12),
                  DateField(controller: _dueDateController, label: 'Due Date'),
                  const SizedBox(height: 12),
                  _SelectRow(
                    label: 'Assignee',
                    value: _assigneeLabel.isEmpty
                        ? 'Select assignee'
                        : _assigneeLabel,
                    onTap: () async {
                      final selected = await Navigator.of(context)
                          .push<SelectOption>(
                            MaterialPageRoute(
                              builder: (_) => const SelectListScreen(
                                title: 'Select Assignee',
                                endpoint: 'users',
                              ),
                            ),
                          );
                      if (selected != null) {
                        setState(() {
                          _assigneeId = selected.id;
                          _assigneeLabel = selected.label;
                        });
                      }
                    },
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _estimatedController,
                    decoration: const InputDecoration(
                      labelText: 'Estimated Hours',
                    ),
                    keyboardType: TextInputType.number,
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _actualController,
                    decoration: const InputDecoration(
                      labelText: 'Actual Hours',
                    ),
                    keyboardType: TextInputType.number,
                  ),
                ],
              ),
              const SizedBox(height: 16),
              FormSection(
                title: 'Execution Details',
                children: [
                  TextFormField(
                    controller: _objectiveController,
                    decoration: const InputDecoration(labelText: 'Objective'),
                    maxLines: 2,
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _outputController,
                    decoration: const InputDecoration(
                      labelText: 'Expected Output',
                    ),
                    maxLines: 2,
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _deliverablesController,
                    decoration: const InputDecoration(
                      labelText: 'Deliverables (one per line)',
                    ),
                    maxLines: 3,
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _referencesController,
                    decoration: const InputDecoration(
                      labelText: 'References (one per line)',
                    ),
                    maxLines: 3,
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _constraintsController,
                    decoration: const InputDecoration(labelText: 'Constraints'),
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
                            const SnackBar(
                              content: Text('Please select a project.'),
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
                            'title': _titleController.text.trim(),
                            'description': _descriptionController.text.trim(),
                            'status': _status,
                            'priority': _priority,
                            'due_date': _dueDateController.text.trim().isEmpty
                                ? null
                                : _dueDateController.text.trim(),
                            'assigned_to': _assigneeId,
                            'estimated_hours':
                                double.tryParse(
                                  _estimatedController.text.trim(),
                                ) ??
                                0,
                            'actual_hours':
                                double.tryParse(
                                  _actualController.text.trim(),
                                ) ??
                                0,
                            'objective': _objectiveController.text.trim(),
                            'expected_output': _outputController.text.trim(),
                            'deliverables': _deliverablesController.text.trim(),
                            'references': _referencesController.text.trim(),
                            'constraints': _constraintsController.text.trim(),
                          };
                          final repo = ref.read(apiRepositoryProvider);
                          Map<String, dynamic> saved;
                          if (isEdit) {
                            saved = await repo.update(
                              'tasks',
                              widget.task!['id'] as int,
                              payload,
                            );
                          } else {
                            saved = await repo.create('tasks', payload);
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
                              content: Text('Failed to save task: $error'),
                            ),
                          );
                        } finally {
                          if (mounted) {
                            setState(() => _saving = false);
                          }
                        }
                      },
                child: Text(_saving ? 'Saving...' : 'Save Task'),
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
