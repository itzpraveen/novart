import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../core/di/providers.dart';
import '../common/app_list_tile.dart';
import '../modules/simple_list_screen.dart';
import '../modules/detail_screen.dart';
import '../projects/projects_list_screen.dart';
import '../site_visits/site_visits_list_screen.dart';
import '../tasks/tasks_list_screen.dart';

final dashboardProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  final repo = ref.watch(apiRepositoryProvider);
  return repo.fetchObject('dashboard/');
});

class DashboardScreen extends ConsumerWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final asyncData = ref.watch(dashboardProvider);
    final session = ref.watch(authControllerProvider).session;
    final userName = session?.user.fullName ?? 'there';
    final permissions = session?.permissions ?? {};
    final isAdmin = session?.user.role == 'admin';
    return Scaffold(
      appBar: AppBar(title: const Text('Dashboard')),
      body: asyncData.when(
        data: (data) => _DashboardBody(
          data: data,
          userName: userName,
          permissions: permissions,
          isAdmin: isAdmin,
        ),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) =>
            Center(child: Text('Failed to load dashboard: $error')),
      ),
    );
  }
}

class _DashboardBody extends StatelessWidget {
  const _DashboardBody({
    required this.data,
    required this.userName,
    required this.permissions,
    required this.isAdmin,
  });

  final Map<String, dynamic> data;
  final String userName;
  final Map<String, bool> permissions;
  final bool isAdmin;

  @override
  Widget build(BuildContext context) {
    final formatter = NumberFormat.compact();
    final totalProjects = data['total_projects'] ?? 0;
    final activeProjects = data['active_projects'] ?? 0;
    final siteVisits = data['site_visits_this_month'] ?? 0;
    final myOpenTasks = data['my_open_tasks_count'] ?? 0;

    final invoicedMonth = data['total_invoiced_month'];
    final receivedMonth = data['total_received_month'];

    final canProjects = isAdmin || permissions['projects'] == true;
    final canSiteVisits = isAdmin || permissions['site_visits'] == true;
    final canFinance =
        isAdmin ||
        permissions['finance'] == true ||
        permissions['invoices'] == true;

    final metrics = <_MetricItem>[
      _MetricItem(
        label: 'Total Projects',
        value: formatter.format(totalProjects),
        icon: Icons.apartment_outlined,
        color: Theme.of(context).colorScheme.primary,
        onTap: canProjects
            ? () => _openScreen(context, const ProjectsListScreen())
            : null,
      ),
      _MetricItem(
        label: 'Active Projects',
        value: formatter.format(activeProjects),
        icon: Icons.work_outline,
        color: Theme.of(context).colorScheme.primary,
        onTap: canProjects
            ? () => _openScreen(
                context,
                const ProjectsListScreen(initialStage: 'active'),
              )
            : null,
      ),
      _MetricItem(
        label: 'Site Visits',
        value: formatter.format(siteVisits),
        icon: Icons.location_on_outlined,
        color: Theme.of(context).colorScheme.tertiary,
        onTap: canSiteVisits
            ? () => _openScreen(context, const SiteVisitsListScreen())
            : null,
      ),
      _MetricItem(
        label: 'My Open Tasks',
        value: formatter.format(myOpenTasks),
        icon: Icons.check_circle_outline,
        color: Theme.of(context).colorScheme.tertiary,
        onTap: canProjects
            ? () => _openScreen(
                context,
                const TasksListScreen(initialStatus: 'open'),
              )
            : null,
      ),
      if (invoicedMonth != null)
        _MetricItem(
          label: 'Invoiced (Month)',
          value: formatter.format(invoicedMonth),
          icon: Icons.receipt_long_outlined,
          color: Theme.of(context).colorScheme.secondary,
          onTap: canFinance
              ? () => _openScreen(
                  context,
                  const SimpleListScreen(
                    title: 'Invoices',
                    endpoint: 'invoices',
                  ),
                )
              : null,
        ),
      if (receivedMonth != null)
        _MetricItem(
          label: 'Received (Month)',
          value: formatter.format(receivedMonth),
          icon: Icons.payments_outlined,
          color: Theme.of(context).colorScheme.secondary,
          onTap: canFinance
              ? () => _openScreen(
                  context,
                  const SimpleListScreen(
                    title: 'Payments',
                    endpoint: 'payments',
                  ),
                )
              : null,
        ),
    ];

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _DashboardHeader(userName: userName),
        const SizedBox(height: 20),
        _SectionHeader(
          title: 'Highlights',
          subtitle: DateFormat('EEE, dd MMM').format(DateTime.now()),
        ),
        const SizedBox(height: 12),
        GridView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: 2,
            crossAxisSpacing: 12,
            mainAxisSpacing: 12,
            childAspectRatio: 1.12,
          ),
          itemCount: metrics.length,
          itemBuilder: (context, index) => _MetricCard(item: metrics[index]),
        ),
        const SizedBox(height: 24),
        _SectionHeader(title: 'Upcoming Tasks'),
        const SizedBox(height: 12),
        _DataList(
          items:
              (data['upcoming_tasks'] as List?)?.cast<Map<String, dynamic>>() ??
              [],
          onTap: (item) => _openDetail(context, 'tasks', item),
        ),
        const SizedBox(height: 24),
        _SectionHeader(title: 'Upcoming Handover'),
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

  void _openScreen(BuildContext context, Widget screen) {
    Navigator.of(context).push(MaterialPageRoute(builder: (_) => screen));
  }
}

class _MetricItem {
  const _MetricItem({
    required this.label,
    required this.value,
    required this.icon,
    required this.color,
    this.onTap,
  });

  final String label;
  final String value;
  final IconData icon;
  final Color color;
  final VoidCallback? onTap;
}

class _MetricCard extends StatelessWidget {
  const _MetricCard({required this.item});

  final _MetricItem item;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Theme.of(context).colorScheme.surface,
      borderRadius: BorderRadius.circular(16),
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: item.onTap,
        child: Ink(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: Theme.of(context).colorScheme.outline.withAlpha(128),
            ),
          ),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  width: 34,
                  height: 34,
                  decoration: BoxDecoration(
                    color: item.color.withAlpha(31),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Icon(item.icon, color: item.color, size: 20),
                ),
                const SizedBox(height: 12),
                Text(
                  item.value,
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  item.label,
                  style: Theme.of(context).textTheme.labelMedium,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _DashboardHeader extends StatelessWidget {
  const _DashboardHeader({required this.userName});

  final String userName;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(
          color: Theme.of(context).colorScheme.outline.withAlpha(128),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Welcome back,', style: Theme.of(context).textTheme.labelLarge),
          const SizedBox(height: 6),
          Text(userName, style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 8),
          Text(
            'Here is a quick snapshot of the workspace.',
            style: Theme.of(context).textTheme.bodyMedium,
          ),
        ],
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({required this.title, this.subtitle});

  final String title;
  final String? subtitle;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Text(title, style: Theme.of(context).textTheme.titleMedium),
        ),
        if (subtitle != null)
          Text(subtitle!, style: Theme.of(context).textTheme.labelMedium),
      ],
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
            (item) => Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: AppListTile(
                title: Text(
                  item['title']?.toString() ??
                      item['name']?.toString() ??
                      'Item',
                ),
                subtitle: Text(
                  item['status']?.toString() ??
                      item['current_stage']?.toString() ??
                      '',
                ),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => onTap(item),
              ),
            ),
          )
          .toList(),
    );
  }
}
