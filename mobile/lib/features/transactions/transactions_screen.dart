import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../core/di/providers.dart';
import '../modules/detail_screen.dart';

enum TransactionFilter { all, income, expense }

final transactionsProvider = FutureProvider<List<Map<String, dynamic>>>((
  ref,
) async {
  final repo = ref.watch(apiRepositoryProvider);
  return repo.fetchList('transactions', params: {'ordering': '-date'});
});

class TransactionsScreen extends ConsumerStatefulWidget {
  const TransactionsScreen({super.key, this.title = 'Cashbook'});

  final String title;

  @override
  ConsumerState<TransactionsScreen> createState() => _TransactionsScreenState();
}

class _TransactionsScreenState extends ConsumerState<TransactionsScreen> {
  final TextEditingController _searchController = TextEditingController();
  TransactionFilter _filter = TransactionFilter.all;

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final asyncTransactions = ref.watch(transactionsProvider);

    return Scaffold(
      appBar: AppBar(title: Text(widget.title)),
      body: asyncTransactions.when(
        data: (transactions) {
          final filtered = _applyFilters(transactions);
          final totals = _Totals.fromTransactions(filtered);
          final rows = _buildRows(filtered);

          return RefreshIndicator(
            onRefresh: () async => ref.invalidate(transactionsProvider),
            child: ListView(
              padding: const EdgeInsets.all(16),
              physics: const AlwaysScrollableScrollPhysics(),
              children: [
                _SummaryStrip(totals: totals),
                const SizedBox(height: 16),
                TextField(
                  controller: _searchController,
                  decoration: InputDecoration(
                    hintText: 'Search cashbook...',
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
                const SizedBox(height: 12),
                Row(
                  children: [
                    Text(
                      '${filtered.length} entries',
                      style: Theme.of(context).textTheme.labelMedium,
                    ),
                    const Spacer(),
                    Text(
                      'Balance ${_formatCurrency(totals.balance)}',
                      style: Theme.of(context).textTheme.labelMedium?.copyWith(
                        color: totals.balance >= 0
                            ? Theme.of(context).colorScheme.tertiary
                            : Theme.of(context).colorScheme.error,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                if (rows.isEmpty)
                  _EmptyState(
                    title: 'No transactions yet',
                    subtitle: 'Cashbook entries will appear here.',
                  )
                else
                  ...rows.map((row) {
                    if (row.isHeader) {
                      return Padding(
                        padding: const EdgeInsets.only(top: 8, bottom: 6),
                        child: Text(
                          row.label,
                          style: Theme.of(context).textTheme.titleSmall,
                        ),
                      );
                    }
                    return Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: _TransactionCard(
                        transaction: row.transaction!,
                        onTap: () {
                          final id = row.transaction!['id'];
                          if (id is int) {
                            Navigator.of(context).push(
                              MaterialPageRoute(
                                builder: (_) => DetailScreen(
                                  endpoint: 'transactions',
                                  id: id,
                                  initialData: row.transaction,
                                ),
                              ),
                            );
                          }
                        },
                      ),
                    );
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

  List<_TransactionRow> _buildRows(List<Map<String, dynamic>> transactions) {
    final rows = <_TransactionRow>[];
    DateTime? currentDate;
    var unknownBucketAdded = false;
    for (final txn in transactions) {
      final date = _parseDate(txn['date']);
      if (date == null) {
        if (!unknownBucketAdded) {
          rows.add(const _TransactionRow.header('Unknown date'));
          unknownBucketAdded = true;
        }
      } else if (currentDate == null || !_isSameDay(date, currentDate)) {
        rows.add(_TransactionRow.header(_formatDate(date)));
        currentDate = date;
      }
      rows.add(_TransactionRow.item(txn));
    }
    return rows;
  }

  bool _isSameDay(DateTime a, DateTime b) {
    return a.year == b.year && a.month == b.month && a.day == b.day;
  }

  DateTime? _parseDate(dynamic value) {
    if (value is String && value.isNotEmpty) {
      return DateTime.tryParse(value);
    }
    return null;
  }

  String _formatDate(DateTime date) {
    return DateFormat('EEE, d MMM').format(date);
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

  String _formatCurrency(num value) {
    final formatter = NumberFormat('#,##0.00', 'en_IN');
    return 'Rs. ${formatter.format(value)}';
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
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: [
          _SummaryCard(
            title: 'Received',
            value: _formatCurrency(totals.income),
            icon: Icons.north_east,
            accent: scheme.tertiary,
          ),
          const SizedBox(width: 12),
          _SummaryCard(
            title: 'Spent',
            value: _formatCurrency(totals.expense),
            icon: Icons.south_west,
            accent: scheme.error,
          ),
          const SizedBox(width: 12),
          _SummaryCard(
            title: 'Balance',
            value: _formatCurrency(totals.balance),
            icon: Icons.account_balance_wallet_outlined,
            accent: totals.balance >= 0 ? scheme.primary : scheme.error,
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
      width: 165,
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

class _TransactionRow {
  const _TransactionRow._(this.isHeader, this.label, this.transaction);

  const _TransactionRow.header(this.label)
    : isHeader = true,
      transaction = null;

  const _TransactionRow.item(this.transaction) : isHeader = false, label = '';

  final bool isHeader;
  final String label;
  final Map<String, dynamic>? transaction;
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
    final subtitle = _subtitle(transaction);

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
        subtitle: Text(subtitle, maxLines: 2, overflow: TextOverflow.ellipsis),
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
            const SizedBox(height: 2),
            Text(
              _humanize(transaction['category']?.toString()),
              style: theme.textTheme.labelSmall,
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

  String _subtitle(Map<String, dynamic> txn) {
    final parts = <String>[];
    final account = (txn['account_detail'] as Map?)?['name']?.toString();
    final project = (txn['related_project_detail'] as Map?)?['name']
        ?.toString();
    final client = (txn['related_client_detail'] as Map?)?['name']?.toString();
    final vendor = (txn['related_vendor_detail'] as Map?)?['name']?.toString();
    final person = (txn['related_person_detail'] as Map?)?['full_name']
        ?.toString();

    if (account != null && account.isNotEmpty) parts.add(account);
    if (project != null && project.isNotEmpty) parts.add(project);
    if (client != null && client.isNotEmpty) parts.add(client);
    if (vendor != null && vendor.isNotEmpty) parts.add(vendor);
    if (person != null && person.isNotEmpty) parts.add(person);

    if (parts.isEmpty) {
      final date = txn['date']?.toString() ?? '';
      return date.isEmpty ? 'Cashbook entry' : date;
    }
    return parts.join(' • ');
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
