import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../core/di/providers.dart';
import '../common/date_field.dart';
import '../common/form_section.dart';
import '../common/select_list_screen.dart';

enum TransactionEntryType { expense, income }

class TransactionEntryScreen extends ConsumerStatefulWidget {
  const TransactionEntryScreen({super.key});

  @override
  ConsumerState<TransactionEntryScreen> createState() =>
      _TransactionEntryScreenState();
}

class _TransactionEntryScreenState
    extends ConsumerState<TransactionEntryScreen> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _dateController;
  late final TextEditingController _amountController;
  late final TextEditingController _descriptionController;
  late final TextEditingController _remarksController;

  TransactionEntryType _type = TransactionEntryType.expense;
  String _category = _expenseCategories.first.value;
  int? _accountId;
  String _accountLabel = '';
  int? _projectId;
  String _projectLabel = '';
  bool _showMore = false;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _dateController = TextEditingController();
    _dateController.text = DateFormat('yyyy-MM-dd').format(DateTime.now());
    _amountController = TextEditingController();
    _descriptionController = TextEditingController();
    _remarksController = TextEditingController();
  }

  @override
  void dispose() {
    _dateController.dispose();
    _amountController.dispose();
    _descriptionController.dispose();
    _remarksController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final categories = _type == TransactionEntryType.expense
        ? _expenseCategories
        : _incomeCategories;

    return Scaffold(
      appBar: AppBar(title: const Text('New Entry')),
      body: SafeArea(
        child: Form(
          key: _formKey,
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              FormSection(
                title: 'Type',
                children: [
                  SegmentedButton<TransactionEntryType>(
                    segments: const [
                      ButtonSegment(
                        value: TransactionEntryType.expense,
                        label: Text('Expense'),
                        icon: Icon(Icons.south_west),
                      ),
                      ButtonSegment(
                        value: TransactionEntryType.income,
                        label: Text('Income'),
                        icon: Icon(Icons.north_east),
                      ),
                    ],
                    selected: {_type},
                    onSelectionChanged: (value) {
                      final next = value.first;
                      if (next == _type) {
                        return;
                      }
                      final nextCategories =
                          next == TransactionEntryType.expense
                          ? _expenseCategories
                          : _incomeCategories;
                      setState(() {
                        _type = next;
                        if (!nextCategories.any(
                          (item) => item.value == _category,
                        )) {
                          _category = nextCategories.first.value;
                        }
                      });
                    },
                  ),
                ],
              ),
              const SizedBox(height: 16),
              FormSection(
                title: 'Details',
                children: [
                  TextFormField(
                    controller: _amountController,
                    decoration: const InputDecoration(labelText: 'Amount *'),
                    keyboardType: const TextInputType.numberWithOptions(
                      decimal: true,
                    ),
                    validator: (value) {
                      if (value == null || value.trim().isEmpty) {
                        return 'Amount is required.';
                      }
                      final parsed = double.tryParse(value.trim());
                      if (parsed == null || parsed <= 0) {
                        return 'Enter a valid amount.';
                      }
                      return null;
                    },
                  ),
                  const SizedBox(height: 12),
                  DateField(controller: _dateController, label: 'Date *'),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _descriptionController,
                    decoration: const InputDecoration(
                      labelText: 'Description *',
                    ),
                    validator: (value) {
                      if (value == null || value.trim().isEmpty) {
                        return 'Description is required.';
                      }
                      return null;
                    },
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    value: _category,
                    decoration: const InputDecoration(labelText: 'Category *'),
                    items: categories
                        .map(
                          (item) => DropdownMenuItem(
                            value: item.value,
                            child: Text(item.label),
                          ),
                        )
                        .toList(),
                    onChanged: (value) {
                      if (value == null) return;
                      setState(() => _category = value);
                    },
                  ),
                  const SizedBox(height: 12),
                  _SelectRow(
                    label: 'Account (optional)',
                    value: _accountLabel.isEmpty
                        ? 'Select account'
                        : _accountLabel,
                    onTap: () async {
                      final selected = await Navigator.of(context)
                          .push<SelectOption>(
                            MaterialPageRoute(
                              builder: (_) => const SelectListScreen(
                                title: 'Select Account',
                                endpoint: 'accounts',
                              ),
                            ),
                          );
                      if (selected != null) {
                        setState(() {
                          _accountId = selected.id;
                          _accountLabel = selected.label;
                        });
                      }
                    },
                    onClear: _accountId == null
                        ? null
                        : () => setState(() {
                            _accountId = null;
                            _accountLabel = '';
                          }),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              TextButton.icon(
                onPressed: () => setState(() => _showMore = !_showMore),
                icon: Icon(
                  _showMore ? Icons.expand_less : Icons.expand_more_outlined,
                ),
                label: Text(_showMore ? 'Less options' : 'More options'),
              ),
              if (_showMore) ...[
                FormSection(
                  title: 'More Options',
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
                      onClear: _projectId == null
                          ? null
                          : () => setState(() {
                              _projectId = null;
                              _projectLabel = '';
                            }),
                    ),
                    const SizedBox(height: 12),
                    TextFormField(
                      controller: _remarksController,
                      decoration: const InputDecoration(
                        labelText: 'Notes (optional)',
                      ),
                      maxLines: 3,
                    ),
                  ],
                ),
              ],
              const SizedBox(height: 16),
              ElevatedButton.icon(
                onPressed: _saving ? null : _save,
                icon: const Icon(Icons.check),
                label: Text(_saving ? 'Saving...' : 'Save Entry'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _save() async {
    if (_dateController.text.trim().isEmpty) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('Date is required.')));
      return;
    }
    if (!_formKey.currentState!.validate()) {
      return;
    }
    setState(() => _saving = true);
    try {
      final amount = double.tryParse(_amountController.text.trim()) ?? 0;
      final userId = ref.read(authControllerProvider).session?.user.id;
      final payload = <String, dynamic>{
        'date': _dateController.text.trim(),
        'description': _descriptionController.text.trim(),
        'category': _category,
        'account': _accountId,
        'related_project': _projectId,
        'remarks': _remarksController.text.trim(),
        'related_person': userId,
        'debit': _type == TransactionEntryType.expense ? amount : 0,
        'credit': _type == TransactionEntryType.income ? amount : 0,
      };
      payload.removeWhere(
        (key, value) =>
            value == null || (value is String && value.trim().isEmpty),
      );
      final repo = ref.read(apiRepositoryProvider);
      final saved = await repo.create('transactions', payload);
      if (!context.mounted) {
        return;
      }
      Navigator.of(context).pop(saved);
    } catch (error) {
      if (!context.mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to save entry: ${_formatError(error)}')),
      );
    } finally {
      if (mounted) {
        setState(() => _saving = false);
      }
    }
  }
}

class _SelectRow extends StatelessWidget {
  const _SelectRow({
    required this.label,
    required this.value,
    required this.onTap,
    this.onClear,
  });

  final String label;
  final String value;
  final VoidCallback onTap;
  final VoidCallback? onClear;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      child: InputDecorator(
        decoration: InputDecoration(
          labelText: label,
          suffixIcon: onClear == null
              ? const Icon(Icons.expand_more)
              : IconButton(icon: const Icon(Icons.clear), onPressed: onClear),
        ),
        child: Text(value),
      ),
    );
  }
}

class _CategoryOption {
  const _CategoryOption(this.value, this.label);

  final String value;
  final String label;
}

const _expenseCategories = [
  _CategoryOption('misc', 'Misc expense'),
  _CategoryOption('project_expense', 'Project expense'),
  _CategoryOption('other_expense', 'Other expense'),
];

const _incomeCategories = [
  _CategoryOption('other_income', 'Other income'),
  _CategoryOption('reimbursement', 'Reimbursement'),
];

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
