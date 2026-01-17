import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../core/di/providers.dart';
import '../expenses/expense_claim_form_screen.dart';
import '../expenses/expense_claims_list_screen.dart';
import '../modules/detail_screen.dart';

enum TransactionFilter { all, income, expense }

final transactionsProvider = FutureProvider<List<Map<String, dynamic>>>((
  ref,
) async {
  final repo = ref.watch(apiRepositoryProvider);
  return repo.fetchList('transactions', params: {'ordering': '-date'});
});

class TransactionsScreen extends ConsumerStatefulWidget {
  const TransactionsScreen({super.key, this.title = 'My Cashbook'});

  final String title;

  @override
  ConsumerState<TransactionsScreen> createState() => _TransactionsScreenState();
}

class _TransactionsScreenState extends ConsumerState<TransactionsScreen> {
  final TextEditingController _searchController = TextEditingController();
  TransactionFilter _filter = TransactionFilter.all;
  bool _showFilters = false;

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final asyncTransactions = ref.watch(transactionsProvider);
    final userId = ref.watch(authControllerProvider).session?.user.id;

    return Scaffold(
      appBar: AppBar(title: Text(widget.title)),
      body: asyncTransactions.when(
        data: (transactions) {
          final filtered = _applyFilters(transactions);
          final totals = _Totals.fromTransactions(filtered);
          final groups = _buildGroups(filtered);

          return RefreshIndicator(
            onRefresh: () async => ref.invalidate(transactionsProvider),
            child: ListView(
              padding: const EdgeInsets.all(16),
              physics: const AlwaysScrollableScrollPhysics(),
              children: [
                _SummaryStrip(totals: totals),
                const SizedBox(height: 10),
                _BalanceRow(balance: totals.balance),
                const SizedBox(height: 16),
                Text(
                  'Expense Claims',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: () {
                          Navigator.of(context).push(
                            MaterialPageRoute(
                              builder: (_) => ExpenseClaimsListScreen(
                                employeeId: userId,
                                title: 'My Expenses',
                              ),
                            ),
                          );
                        },
                        icon: const Icon(Icons.receipt_long_outlined),
                        label: const Text('View claims'),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: ElevatedButton.icon(
                        onPressed: () async {
                          await Navigator.of(
                            context,
                          ).push<Map<String, dynamic>>(
                            MaterialPageRoute(
                              builder: (_) => const ExpenseClaimFormScreen(),
                            ),
                          );
                        },
                        icon: const Icon(Icons.add),
                        label: const Text('New claim'),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: _searchController,
                        decoration: InputDecoration(
                          hintText: 'Search transactions...',
                          prefixIcon: const Icon(Icons.search),
                          suffixIcon: _searchController.text.isEmpty
                              ? null
                              : IconButton(
                                  icon: const Icon(Icons.close),
                                  onPressed: () {
                                    _searchController.clear();
                                    setState(() {});
                                  },
                                ),
                        ),
                        onChanged: (_) => setState(() {}),
                      ),
                    ),
                    const SizedBox(width: 12),
                    IconButton(
                      onPressed: () =>
                          setState(() => _showFilters = !_showFilters),
                      icon: Icon(
                        _showFilters
                            ? Icons.filter_alt_off_outlined
                            : Icons.filter_alt_outlined,
                      ),
                    ),
                  ],
                ),
                if (_showFilters) ...[
                  const SizedBox(height: 12),
                  SegmentedButton<TransactionFilter>(
                    segments: const [
                      ButtonSegment(
                        value: TransactionFilter.all,
                        label: Text('All'),
                        icon: Icon(Icons.list_alt),
                      ),
                      ButtonSegment(
                        value: TransactionFilter.income,
                        label: Text('Income'),
                        icon: Icon(Icons.trending_up),
                      ),
                      ButtonSegment(
                        value: TransactionFilter.expense,
                        label: Text('Expense'),
                        icon: Icon(Icons.trending_down),
                      ),
                    ],
                    selected: {_filter},
                    onSelectionChanged: (value) =>
                        setState(() => _filter = value.first),
                  ),
                ],
                const SizedBox(height: 16),
                _SectionHeader(title: 'Transactions', count: filtered.length),
                const SizedBox(height: 8),
                if (groups.isEmpty)
                  _EmptyState(
                    title: 'No transactions yet',
                    subtitle: 'Cashbook entries will appear here.',
                  )
                else
                  ...groups.expand((group) {
                    return [
                      _GroupHeader(
                        label: group.label,
                        count: group.items.length,
                      ),
                      const SizedBox(height: 8),
                      ...group.items.map(
                        (transaction) => Padding(
                          padding: const EdgeInsets.only(bottom: 12),
                          child: _TransactionCard(
                            transaction: transaction,
                            onTap: () {
                              final id = transaction['id'];
                              if (id is int) {
                                Navigator.of(context).push(
                                  MaterialPageRoute(
                                    builder: (_) => DetailScreen(
                                      endpoint: 'transactions',
                                      id: id,
                                      initialData: transaction,
                                    ),
                                  ),
                                );
                              }
                            },
                          ),
                        ),
                      ),
                    ];
                  }),
              ],
            ),
          );
        },
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) =>
            Center(child: Text('Failed to load cashbook: $error')),
      ),
    );
  }

  List<Map<String, dynamic>> _applyFilters(
    List<Map<String, dynamic>> transactions,
  ) {
    final term = _searchController.text.trim().toLowerCase();
    final filtered = transactions.where((txn) {
      if (_filter == TransactionFilter.income && !_isIncome(txn)) {
        return false;
      }
      if (_filter == TransactionFilter.expense && !_isExpense(txn)) {
        return false;
      }
      if (term.isEmpty) {
        return true;
      }
      return _searchableText(txn).contains(term);
    }).toList();
    return filtered;
  }

  bool _isIncome(Map<String, dynamic> txn) {
    return _numValue(txn['credit']) > 0;
  }

  bool _isExpense(Map<String, dynamic> txn) {
    return _numValue(txn['debit']) > 0;
  }

  String _searchableText(Map<String, dynamic> txn) {
    final buffer = StringBuffer();
    void add(dynamic value) {
      if (value == null) return;
      buffer.write(value.toString().toLowerCase());
      buffer.write(' ');
    }

    add(txn['description']);
    add(_humanize(txn['category']?.toString()));
    add(txn['subcategory']);
    add((txn['account_detail'] as Map?)?['name']);
    add((txn['related_project_detail'] as Map?)?['name']);
    add((txn['related_client_detail'] as Map?)?['name']);
    add((txn['related_vendor_detail'] as Map?)?['name']);
    add((txn['related_person_detail'] as Map?)?['full_name']);
    return buffer.toString();
  }

  List<_TransactionGroup> _buildGroups(
    List<Map<String, dynamic>> transactions,
  ) {
    final groups = <_TransactionGroup>[];
    _TransactionGroup? current;
    for (final txn in transactions) {
      final date = _parseDate(txn['date']);
      final label = date == null ? 'Unknown date' : _formatDate(date);
      if (current == null || current.label != label) {
        current = _TransactionGroup(label: label, items: []);
        groups.add(current);
      }
      current.items.add(txn);
    }
    return groups;
  }

  DateTime? _parseDate(dynamic value) {
    if (value is String && value.isNotEmpty) {
      return DateTime.tryParse(value);
    }
    return null;
  }

  String _formatDate(DateTime date) {
    return DateFormat('EEE, d MMM yyyy').format(date);
  }

  String _humanize(String? value) {
    if (value == null || value.trim().isEmpty) return '';
    return value
        .split('_')
        .map(
          (word) => word.isEmpty
              ? ''
              : '${word[0].toUpperCase()}${word.substring(1)}',
        )
        .join(' ');
  }

  double _numValue(dynamic value) {
    if (value is num) {
      return value.toDouble();
    }
    return double.tryParse(value?.toString() ?? '') ?? 0;
  }
}

class _Totals {
  const _Totals({required this.income, required this.expense});

  final double income;
  final double expense;

  double get balance => income - expense;

  factory _Totals.fromTransactions(List<Map<String, dynamic>> transactions) {
    double income = 0;
    double expense = 0;
    for (final txn in transactions) {
      final credit = _value(txn['credit']);
      final debit = _value(txn['debit']);
      income += credit;
      expense += debit;
    }
    return _Totals(income: income, expense: expense);
  }

  static double _value(dynamic value) {
    if (value is num) return value.toDouble();
    return double.tryParse(value?.toString() ?? '') ?? 0;
  }
}

class _SummaryStrip extends StatelessWidget {
  const _SummaryStrip({required this.totals});

  final _Totals totals;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Row(
      children: [
        Expanded(
          child: _SummaryCard(
            title: 'Spent',
            value: _formatCurrency(totals.expense),
            icon: Icons.south_west,
            accent: scheme.error,
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _SummaryCard(
            title: 'Received',
            value: _formatCurrency(totals.income),
            icon: Icons.north_east,
            accent: scheme.tertiary,
          ),
        ),
      ],
    );
  }

  String _formatCurrency(num value) {
    final formatter = NumberFormat('#,##0.00', 'en_IN');
    return 'Rs. ${formatter.format(value)}';
  }
}

class _SummaryCard extends StatelessWidget {
  const _SummaryCard({
    required this.title,
    required this.value,
    required this.icon,
    required this.accent,
  });

  final String title;
  final String value;
  final IconData icon;
  final Color accent;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: Theme.of(context).colorScheme.outline.withAlpha(120),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 34,
            height: 34,
            decoration: BoxDecoration(
              color: accent.withAlpha(24),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(icon, color: accent, size: 18),
          ),
          const SizedBox(height: 12),
          Text(
            value,
            style: Theme.of(
              context,
            ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 4),
          Text(title, style: Theme.of(context).textTheme.labelMedium),
        ],
      ),
    );
  }
}

class _BalanceRow extends StatelessWidget {
  const _BalanceRow({required this.balance});

  final double balance;

  @override
  Widget build(BuildContext context) {
    final color = balance >= 0
        ? Theme.of(context).colorScheme.tertiary
        : Theme.of(context).colorScheme.error;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: Theme.of(context).colorScheme.outline.withAlpha(120),
        ),
      ),
      child: Row(
        children: [
          const Icon(Icons.account_balance_wallet_outlined, size: 18),
          const SizedBox(width: 8),
          Text('Balance', style: Theme.of(context).textTheme.labelMedium),
          const Spacer(),
          Text(
            _formatCurrency(balance),
            style: Theme.of(context).textTheme.titleSmall?.copyWith(
              color: color,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }

  String _formatCurrency(num value) {
    final formatter = NumberFormat('#,##0.00', 'en_IN');
    return 'Rs. ${formatter.format(value)}';
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({required this.title, required this.count});

  final String title;
  final int count;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Text(title, style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(width: 8),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.surface,
            borderRadius: BorderRadius.circular(999),
            border: Border.all(
              color: Theme.of(context).colorScheme.outline.withAlpha(120),
            ),
          ),
          child: Text(
            count.toString(),
            style: Theme.of(context).textTheme.labelSmall,
          ),
        ),
      ],
    );
  }
}

class _GroupHeader extends StatelessWidget {
  const _GroupHeader({required this.label, required this.count});

  final String label;
  final int count;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Text(label, style: Theme.of(context).textTheme.labelLarge),
        const Spacer(),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.surface,
            borderRadius: BorderRadius.circular(999),
            border: Border.all(
              color: Theme.of(context).colorScheme.outline.withAlpha(120),
            ),
          ),
          child: Text(
            '$count ${count == 1 ? 'item' : 'items'}',
            style: Theme.of(context).textTheme.labelSmall,
          ),
        ),
      ],
    );
  }
}

class _TransactionGroup {
  _TransactionGroup({required this.label, required this.items});

  final String label;
  final List<Map<String, dynamic>> items;
}

class _TagChip extends StatelessWidget {
  const _TagChip({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(label, style: Theme.of(context).textTheme.labelSmall),
    );
  }
}

class _TransactionCard extends StatelessWidget {
  const _TransactionCard({required this.transaction, this.onTap});

  final Map<String, dynamic> transaction;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isIncome = _value(transaction['credit']) > 0;
    final amount = isIncome
        ? _value(transaction['credit'])
        : _value(transaction['debit']);
    final accent = isIncome
        ? theme.colorScheme.tertiary
        : theme.colorScheme.error;
    final title = _title(transaction);
    final tags = _tags(transaction);

    return Card(
      child: ListTile(
        onTap: onTap,
        leading: CircleAvatar(
          backgroundColor: accent.withAlpha(28),
          child: Icon(
            isIncome ? Icons.north_east : Icons.south_west,
            color: accent,
            size: 18,
          ),
        ),
        title: Text(title, maxLines: 1, overflow: TextOverflow.ellipsis),
        subtitle: tags.isEmpty
            ? Text('Cashbook entry', style: theme.textTheme.bodySmall)
            : Wrap(
                spacing: 6,
                runSpacing: 4,
                children: tags.map((tag) => _TagChip(label: tag)).toList(),
              ),
        trailing: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Text(
              '${isIncome ? '+' : '-'}${_formatCurrency(amount)}',
              style: theme.textTheme.titleSmall?.copyWith(
                color: accent,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
        ),
      ),
    );
  }

  String _title(Map<String, dynamic> txn) {
    final description = txn['description']?.toString().trim();
    if (description != null && description.isNotEmpty) {
      return description;
    }
    final category = _humanize(txn['category']?.toString());
    return category.isEmpty ? 'Transaction' : category;
  }

  List<String> _tags(Map<String, dynamic> txn) {
    final tags = <String>[];
    final category = _humanize(txn['category']?.toString());
    if (category.isNotEmpty) {
      tags.add(category);
    }
    final account = (txn['account_detail'] as Map?)?['name']?.toString();
    if (account != null && account.isNotEmpty) {
      tags.add(account);
    }

    void addFallbackTag(String? value) {
      if (tags.length >= 2) return;
      if (value == null || value.isEmpty) return;
      tags.add(value);
    }

    addFallbackTag(
      (txn['related_project_detail'] as Map?)?['name']?.toString(),
    );
    addFallbackTag((txn['related_client_detail'] as Map?)?['name']?.toString());
    addFallbackTag((txn['related_vendor_detail'] as Map?)?['name']?.toString());
    addFallbackTag(
      (txn['related_person_detail'] as Map?)?['full_name']?.toString(),
    );
    return tags;
  }

  String _humanize(String? value) {
    if (value == null || value.trim().isEmpty) return '';
    return value
        .split('_')
        .map(
          (word) => word.isEmpty
              ? ''
              : '${word[0].toUpperCase()}${word.substring(1)}',
        )
        .join(' ');
  }

  String _formatCurrency(num value) {
    final formatter = NumberFormat('#,##0.00', 'en_IN');
    return 'Rs. ${formatter.format(value)}';
  }

  double _value(dynamic value) {
    if (value is num) return value.toDouble();
    return double.tryParse(value?.toString() ?? '') ?? 0;
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState({required this.title, required this.subtitle});

  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: Theme.of(context).colorScheme.outline.withAlpha(120),
        ),
      ),
      child: Column(
        children: [
          Icon(
            Icons.account_balance_wallet_outlined,
            size: 36,
            color: Theme.of(context).colorScheme.primary,
          ),
          const SizedBox(height: 12),
          Text(title, style: Theme.of(context).textTheme.titleSmall),
          const SizedBox(height: 6),
          Text(
            subtitle,
            style: Theme.of(context).textTheme.bodySmall,
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}
