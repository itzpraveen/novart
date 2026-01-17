import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/di/providers.dart';
import '../common/select_list_screen.dart';
import 'expense_claim_detail_screen.dart';
import 'expense_claim_form_screen.dart';

class ExpenseClaimQuery {
  ExpenseClaimQuery(this.employeeId, this.status, this.projectId);

  final int? employeeId;
  final String status;
  final int? projectId;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is ExpenseClaimQuery &&
          employeeId == other.employeeId &&
          status == other.status &&
          projectId == other.projectId;

  @override
  int get hashCode => Object.hash(employeeId, status, projectId);
}

final expenseClaimsProvider =
    FutureProvider.family<List<Map<String, dynamic>>, ExpenseClaimQuery>((
      ref,
      query,
    ) async {
      final repo = ref.watch(apiRepositoryProvider);
      final params = <String, dynamic>{};
      if (query.employeeId != null) {
        params['employee'] = query.employeeId;
      }
      if (query.status.isNotEmpty) {
        params['status'] = query.status;
      }
      if (query.projectId != null) {
        params['project'] = query.projectId;
      }
      return repo.fetchList(
        'expense-claims',
        params: params.isEmpty ? null : params,
      );
    });

class ExpenseClaimsListScreen extends ConsumerStatefulWidget {
  const ExpenseClaimsListScreen({
    super.key,
    this.employeeId,
    this.title = 'Expense Claims',
  });

  final int? employeeId;
  final String title;

  @override
  ConsumerState<ExpenseClaimsListScreen> createState() =>
      _ExpenseClaimsListScreenState();
}

class _ExpenseClaimsListScreenState
    extends ConsumerState<ExpenseClaimsListScreen> {
  String _search = '';
  String _status = '';
  int? _projectId;
  String _projectLabel = '';

  @override
  Widget build(BuildContext context) {
    final asyncClaims = ref.watch(
      expenseClaimsProvider(
        ExpenseClaimQuery(widget.employeeId, _status, _projectId),
      ),
    );

    return Scaffold(
      appBar: AppBar(title: Text(widget.title)),
      floatingActionButton: FloatingActionButton(
        onPressed: () async {
          final created = await Navigator.of(context)
              .push<Map<String, dynamic>>(
                MaterialPageRoute(
                  builder: (_) => const ExpenseClaimFormScreen(),
                ),
              );
          if (created != null) {
            ref.invalidate(expenseClaimsProvider);
          }
        },
        child: const Icon(Icons.add),
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              children: [
                TextField(
                  decoration: const InputDecoration(
                    hintText: 'Search expenses...',
                    prefixIcon: Icon(Icons.search),
                  ),
                  onChanged: (value) => setState(() => _search = value.trim()),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  key: ValueKey(_status),
                  initialValue: _status.isEmpty ? null : _status,
                  decoration: const InputDecoration(labelText: 'Status'),
                  items: const [
                    DropdownMenuItem(value: '', child: Text('All statuses')),
                    DropdownMenuItem(
                      value: 'submitted',
                      child: Text('Submitted'),
                    ),
                    DropdownMenuItem(
                      value: 'approved',
                      child: Text('Approved'),
                    ),
                    DropdownMenuItem(
                      value: 'rejected',
                      child: Text('Rejected'),
                    ),
                    DropdownMenuItem(value: 'paid', child: Text('Paid')),
                  ],
                  onChanged: (value) => setState(() => _status = value ?? ''),
                ),
                const SizedBox(height: 12),
                _SelectRow(
                  label: 'Project',
                  value: _projectLabel.isEmpty ? 'All projects' : _projectLabel,
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
              ],
            ),
          ),
          Expanded(
            child: asyncClaims.when(
              data: (claims) {
                final filtered = _applySearch(claims);
                if (filtered.isEmpty) {
                  return const Center(child: Text('No expense claims found.'));
                }
                return RefreshIndicator(
                  onRefresh: () async => ref.invalidate(expenseClaimsProvider),
                  child: ListView.separated(
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    itemBuilder: (context, index) {
                      final claim = filtered[index];
                      return ListTile(
                        tileColor: Theme.of(context).colorScheme.surface,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                        title: Text(_titleFor(claim)),
                        subtitle: Text(_subtitleFor(claim)),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () {
                          final id = claim['id'];
                          if (id is int) {
                            Navigator.of(context).push(
                              MaterialPageRoute(
                                builder: (_) =>
                                    ExpenseClaimDetailScreen(claimId: id),
                              ),
                            );
                          }
                        },
                      );
                    },
                    separatorBuilder: (context, index) =>
                        const SizedBox(height: 12),
                    itemCount: filtered.length,
                  ),
                );
              },
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (error, _) =>
                  Center(child: Text('Failed to load expenses: $error')),
            ),
          ),
        ],
      ),
    );
  }

  List<Map<String, dynamic>> _applySearch(List<Map<String, dynamic>> claims) {
    if (_search.isEmpty) {
      return claims;
    }
    final term = _search.toLowerCase();
    return claims.where((claim) {
      final desc = claim['description']?.toString().toLowerCase() ?? '';
      final category = claim['category']?.toString().toLowerCase() ?? '';
      final project = claim['project_detail'] as Map<String, dynamic>?;
      final projectName = project?['name']?.toString().toLowerCase() ?? '';
      final employee = claim['employee_detail'] as Map<String, dynamic>?;
      final employeeName =
          employee?['full_name']?.toString().toLowerCase() ?? '';
      return desc.contains(term) ||
          category.contains(term) ||
          projectName.contains(term) ||
          employeeName.contains(term);
    }).toList();
  }

  String _titleFor(Map<String, dynamic> claim) {
    final amount = claim['amount']?.toString() ?? '';
    final category = claim['category']?.toString() ?? 'Expense';
    if (amount.isEmpty) {
      return category;
    }
    return '$category • $amount';
  }

  String _subtitleFor(Map<String, dynamic> claim) {
    final date = claim['expense_date']?.toString() ?? '';
    final status = claim['status']?.toString() ?? '';
    final project = claim['project_detail'] as Map<String, dynamic>?;
    final projectName = project?['name']?.toString() ?? '';
    final parts = [
      date,
      status,
      projectName,
    ].where((value) => value.trim().isNotEmpty).toList();
    return parts.isEmpty ? 'Expense claim' : parts.join(' • ');
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
              ? null
              : IconButton(icon: const Icon(Icons.clear), onPressed: onClear),
        ),
        child: Row(
          children: [
            Expanded(child: Text(value)),
            const Icon(Icons.expand_more),
          ],
        ),
      ),
    );
  }
}
