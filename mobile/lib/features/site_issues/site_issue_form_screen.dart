import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/di/providers.dart';
import '../common/date_field.dart';
import '../common/form_section.dart';
import '../common/select_list_screen.dart';

class SiteIssueFormScreen extends ConsumerStatefulWidget {
  const SiteIssueFormScreen({super.key, this.issue});

  final Map<String, dynamic>? issue;

  @override
  ConsumerState<SiteIssueFormScreen> createState() =>
      _SiteIssueFormScreenState();
}

class _SiteIssueFormScreenState extends ConsumerState<SiteIssueFormScreen> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _titleController;
  late final TextEditingController _descriptionController;
  late final TextEditingController _raisedOnController;
  late final TextEditingController _resolvedOnController;

  int? _projectId;
  int? _siteVisitId;
  String _projectLabel = '';
  String _siteVisitLabel = '';
  String _status = 'open';
  bool _saving = false;

  static const statusOptions = ['open', 'in_progress', 'resolved'];

  @override
  void initState() {
    super.initState();
    final issue = widget.issue ?? {};
    _titleController = TextEditingController(
      text: issue['title']?.toString() ?? '',
    );
    _descriptionController = TextEditingController(
      text: issue['description']?.toString() ?? '',
    );
    _raisedOnController = TextEditingController(
      text: issue['raised_on']?.toString() ?? '',
    );
    _resolvedOnController = TextEditingController(
      text: issue['resolved_on']?.toString() ?? '',
    );

    _projectId = issue['project'] as int?;
    _siteVisitId = issue['site_visit'] as int?;
    _projectLabel = issue['project_detail']?['name']?.toString() ?? '';
    _siteVisitLabel = _formatVisitLabel(issue['site_visit_detail']);
    _status = issue['status']?.toString() ?? 'open';
  }

  @override
  void dispose() {
    _titleController.dispose();
    _descriptionController.dispose();
    _raisedOnController.dispose();
    _resolvedOnController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isEdit = widget.issue != null;
    final isResolved = _status == 'resolved';

    return Scaffold(
      appBar: AppBar(
        title: Text(isEdit ? 'Edit Site Issue' : 'New Site Issue'),
      ),
      body: SafeArea(
        child: Form(
          key: _formKey,
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              FormSection(
                title: 'Issue Details',
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
                          _siteVisitId = null;
                          _siteVisitLabel = '';
                        });
                      }
                    },
                  ),
                  const SizedBox(height: 12),
                  _SelectRow(
                    label: 'Site Visit',
                    value: _siteVisitLabel.isEmpty
                        ? 'Select visit (optional)'
                        : _siteVisitLabel,
                    onTap: () async {
                      final selected = await Navigator.of(context)
                          .push<SelectOption>(
                            MaterialPageRoute(
                              builder: (_) => const SelectListScreen(
                                title: 'Select Site Visit',
                                endpoint: 'site-visits',
                              ),
                            ),
                          );
                      if (selected != null) {
                        setState(() {
                          _siteVisitId = selected.id;
                          _siteVisitLabel = _formatVisitLabel(selected.raw);
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
                        return 'Issue title is required.';
                      }
                      return null;
                    },
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
                    onChanged: (value) {
                      if (value == null) {
                        return;
                      }
                      setState(() => _status = value);
                    },
                  ),
                  const SizedBox(height: 12),
                  DateField(
                    controller: _raisedOnController,
                    label: 'Raised On *',
                  ),
                  if (isResolved) ...[
                    const SizedBox(height: 12),
                    DateField(
                      controller: _resolvedOnController,
                      label: 'Resolved On',
                    ),
                  ],
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
                        if (_projectId == null) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(content: Text('Select a project.')),
                          );
                          return;
                        }
                        if (_raisedOnController.text.trim().isEmpty) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                              content: Text('Raised date is required.'),
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
                            'site_visit': _siteVisitId,
                            'title': _titleController.text.trim(),
                            'description': _descriptionController.text.trim(),
                            'raised_on': _raisedOnController.text.trim(),
                            'status': _status,
                            'resolved_on':
                                _status == 'resolved' &&
                                    _resolvedOnController.text.trim().isNotEmpty
                                ? _resolvedOnController.text.trim()
                                : null,
                          };
                          final repo = ref.read(apiRepositoryProvider);
                          Map<String, dynamic> saved;
                          if (isEdit) {
                            saved = await repo.update(
                              'site-issues',
                              widget.issue!['id'] as int,
                              payload,
                            );
                          } else {
                            saved = await repo.create('site-issues', payload);
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
                                'Failed to save site issue: $error',
                              ),
                            ),
                          );
                        } finally {
                          if (mounted) {
                            setState(() => _saving = false);
                          }
                        }
                      },
                child: Text(_saving ? 'Saving...' : 'Save Site Issue'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _formatVisitLabel(Map<String, dynamic>? visit) {
    if (visit == null) {
      return '';
    }
    final date = visit['visit_date']?.toString() ?? '';
    final projectId =
        (visit['project_id'] ?? visit['project'])?.toString() ?? '';
    final projectName = visit['project_detail']?['name']?.toString() ?? '';
    final projectLabel = projectName.isNotEmpty
        ? projectName
        : (projectId.isEmpty ? '' : 'Project $projectId');
    if (projectLabel.isEmpty) {
      return date;
    }
    return date.isEmpty ? projectLabel : '$date • $projectLabel';
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
