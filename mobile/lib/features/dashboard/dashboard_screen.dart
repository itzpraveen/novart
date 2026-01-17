import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../core/di/providers.dart';
import '../modules/detail_screen.dart';

final dashboardProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  final repo = ref.watch(apiRepositoryProvider);
  return repo.fetchObject('dashboard/');
});

class DashboardScreen extends ConsumerWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final asyncData = ref.watch(dashboardProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Dashboard')),
      body: asyncData.when(
        data: (data) => _DashboardBody(data: data),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) =>
            Center(child: Text('Failed to load dashboard: $error')),
      ),
    );
  }
}

class _DashboardBody extends StatelessWidget {
  const _DashboardBody({required this.data});

  final Map<String, dynamic> data;

  @override
  Widget build(BuildContext context) {
    final formatter = NumberFormat.compact();
    final totalProjects = data['total_projects'] ?? 0;
    final activeProjects = data['active_projects'] ?? 0;
    final siteVisits = data['site_visits_this_month'] ?? 0;
    final myOpenTasks = data['my_open_tasks_count'] ?? 0;

    final invoicedMonth = data['total_invoiced_month'];
    final receivedMonth = data['total_received_month'];

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Wrap(
          spacing: 12,
          runSpacing: 12,
          children: [
            _MetricCard(
              label: 'Total Projects',
              value: formatter.format(totalProjects),
            ),
            _MetricCard(
              label: 'Active Projects',
              value: formatter.format(activeProjects),
            ),
            _MetricCard(
              label: 'Site Visits (Month)',
              value: formatter.format(siteVisits),
            ),
            _MetricCard(
              label: 'My Open Tasks',
              value: formatter.format(myOpenTasks),
            ),
            if (invoicedMonth != null)
              _MetricCard(
                label: 'Invoiced (Month)',
                value: formatter.format(invoicedMonth),
              ),
            if (receivedMonth != null)
              _MetricCard(
                label: 'Received (Month)',
                value: formatter.format(receivedMonth),
              ),
          ],
        ),
        const SizedBox(height: 24),
        Text('Upcoming Tasks', style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 12),
        _DataList(
          items:
              (data['upcoming_tasks'] as List?)?.cast<Map<String, dynamic>>() ??
              [],
          onTap: (item) => _openDetail(context, 'tasks', item),
        ),
        const SizedBox(height: 24),
        Text(
          'Upcoming Handover',
          style: Theme.of(context).textTheme.titleMedium,
        ),
        const SizedBox(height: 12),
        _DataList(
          items:
              (data['upcoming_handover'] as List?)
                  ?.cast<Map<String, dynamic>>() ??
              [],
          onTap: (item) => _openDetail(context, 'projects', item),
        ),
      ],
    );
  }

  void _openDetail(
    BuildContext context,
    String endpoint,
    Map<String, dynamic> item,
  ) {
    final id = item['id'];
    if (id is int) {
      Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => DetailScreen(endpoint: endpoint, id: id),
        ),
      );
    }
  }
}

class _MetricCard extends StatelessWidget {
  const _MetricCard({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: (MediaQuery.of(context).size.width - 44) / 2,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: Theme.of(context).textTheme.labelMedium),
          const SizedBox(height: 10),
          Text(
            value,
            style: Theme.of(
              context,
            ).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w700),
          ),
        ],
      ),
    );
  }
}

class _DataList extends StatelessWidget {
  const _DataList({required this.items, required this.onTap});

  final List<Map<String, dynamic>> items;
  final void Function(Map<String, dynamic>) onTap;

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) {
      return const Text('No items found.');
    }

    return Column(
      children: items
          .map(
            (item) => Card(
              margin: const EdgeInsets.only(bottom: 12),
              child: ListTile(
                title: Text(
                  item['title']?.toString() ??
                      item['name']?.toString() ??
                      'Item',
                ),
                subtitle: Text(item['status']?.toString() ?? ''),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => onTap(item),
              ),
            ),
          )
          .toList(),
    );
  }
}
