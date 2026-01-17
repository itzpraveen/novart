import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:dio/dio.dart';

import '../../core/di/providers.dart';
import '../common/date_field.dart';
import '../common/form_section.dart';
import '../common/select_list_screen.dart';

class ExpenseClaimFormScreen extends ConsumerStatefulWidget {
  const ExpenseClaimFormScreen({super.key, this.claim});

  final Map<String, dynamic>? claim;

  @override
  ConsumerState<ExpenseClaimFormScreen> createState() =>
      _ExpenseClaimFormScreenState();
}

class _ExpenseClaimFormScreenState
    extends ConsumerState<ExpenseClaimFormScreen> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _dateController;
  late final TextEditingController _amountController;
  late final TextEditingController _categoryController;
  late final TextEditingController _descriptionController;

  int? _projectId;
  String _projectLabel = '';
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    final claim = widget.claim ?? {};
    _dateController = TextEditingController(
      text: claim['expense_date']?.toString() ?? '',
    );
    _amountController = TextEditingController(
      text: claim['amount']?.toString() ?? '',
    );
    _categoryController = TextEditingController(
      text: claim['category']?.toString() ?? '',
    );
    _descriptionController = TextEditingController(
      text: claim['description']?.toString() ?? '',
    );
    _projectId = claim['project'] as int?;
    _projectLabel = claim['project_detail']?['name']?.toString() ?? '';
  }

  @override
  void dispose() {
    _dateController.dispose();
    _amountController.dispose();
    _categoryController.dispose();
    _descriptionController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isEdit = widget.claim != null;

    return Scaffold(
      appBar: AppBar(
        title: Text(isEdit ? 'Edit Expense Claim' : 'New Expense Claim'),
      ),
      body: SafeArea(
        child: Form(
          key: _formKey,
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              FormSection(
                title: 'Expense Details',
                children: [
                  _SelectRow(
                    label: 'Project (optional)',
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
                    controller: _dateController,
                    label: 'Expense Date *',
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _amountController,
                    decoration: const InputDecoration(labelText: 'Amount *'),
                    keyboardType: TextInputType.number,
                    validator: (value) {
                      if (value == null || value.trim().isEmpty) {
                        return 'Amount is required.';
                      }
                      return null;
                    },
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _categoryController,
                    decoration: const InputDecoration(labelText: 'Category'),
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
                        if (_dateController.text.trim().isEmpty) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                              content: Text('Expense date is required.'),
                            ),
                          );
                          return;
                        }
                        if (!_formKey.currentState!.validate()) {
                          return;
                        }
                        setState(() => _saving = true);
                        try {
                          final userId = ref
                              .read(authControllerProvider)
                              .session
                              ?.user
                              .id;
                          final payload = {
                            'project': _projectId,
                            'expense_date': _dateController.text.trim(),
                            'amount':
                                double.tryParse(
                                  _amountController.text.trim(),
                                ) ??
                                0,
                            'category': _categoryController.text.trim(),
                            'description': _descriptionController.text.trim(),
                            if (!isEdit && userId != null) 'employee': userId,
                          };
                          final repo = ref.read(apiRepositoryProvider);
                          Map<String, dynamic> saved;
                          if (isEdit) {
                            saved = await repo.patch(
                              'expense-claims',
                              widget.claim!['id'] as int,
                              payload,
                            );
                          } else {
                            saved = await repo.create(
                              'expense-claims',
                              payload,
                            );
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
                                'Failed to save expense claim: ${_formatError(error)}',
                              ),
                            ),
                          );
                        } finally {
                          if (mounted) {
                            setState(() => _saving = false);
                          }
                        }
                      },
                child: Text(_saving ? 'Saving...' : 'Save Expense Claim'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

String _formatError(Object error) {
  if (error is DioException) {
    final data = error.response?.data;
    if (data is Map<String, dynamic>) {
      final detail = data['detail']?.toString();
      if (detail != null && detail.isNotEmpty) {
        return detail;
      }
      return data.values.map((value) => value.toString()).join(' ');
    }
    if (data is String && data.isNotEmpty) {
      return data;
    }
    return error.message ?? 'Request failed';
  }
  return error.toString();
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
