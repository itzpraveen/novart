import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../core/di/providers.dart';
import '../../core/theme/app_theme.dart';
import '../common/app_list_tile.dart';
import '../common/shimmer_loading.dart';
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
      appBar: AppBar(
        title: const Text('Dashboard'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () {
              HapticFeedback.lightImpact();
              ref.invalidate(dashboardProvider);
            },
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          HapticFeedback.mediumImpact();
          ref.invalidate(dashboardProvider);
        },
        child: asyncData.when(
          data: (data) => _DashboardBody(
            data: data,
            userName: userName,
            permissions: permissions,
            isAdmin: isAdmin,
          ),
          loading: () => const _DashboardSkeleton(),
          error: (error, _) => _DashboardError(
            error: error.toString(),
            onRetry: () => ref.invalidate(dashboardProvider),
          ),
        ),
      ),
    );
  }
}

class _DashboardSkeleton extends StatelessWidget {
  const _DashboardSkeleton();

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      physics: const AlwaysScrollableScrollPhysics(),
      children: [
        ShimmerLoading(
          child: Container(
            height: 100,
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(18),
            ),
          ),
        ),
        const SizedBox(height: 20),
        Row(
          children: [
            ShimmerLoading(
              child: Container(
                height: 16,
                width: 80,
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(4),
                ),
              ),
            ),
            const Spacer(),
            ShimmerLoading(
              child: Container(
                height: 14,
                width: 100,
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(4),
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        const SkeletonMetricsGrid(itemCount: 4),
        const SizedBox(height: 24),
        ShimmerLoading(
          child: Container(
            height: 16,
            width: 120,
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(4),
            ),
          ),
        ),
        const SizedBox(height: 12),
        const SkeletonList(itemCount: 3),
      ],
    );
  }
}

class _DashboardError extends StatelessWidget {
  const _DashboardError({required this.error, required this.onRetry});

  final String error;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: AppTheme.error.withAlpha(15),
                borderRadius: BorderRadius.circular(50),
              ),
              child: Icon(
                Icons.cloud_off_outlined,
                size: 48,
                color: AppTheme.error.withAlpha(180),
              ),
            ),
            const SizedBox(height: 20),
            Text(
              'Unable to load dashboard',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            Text(
              error,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: AppTheme.onSurface.withAlpha(140),
              ),
            ),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh, size: 18),
              label: const Text('Try again'),
            ),
          ],
        ),
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
      physics: const AlwaysScrollableScrollPhysics(),
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
          itemBuilder: (context, index) => _MetricCard(
            item: metrics[index],
            index: index,
          ),
        ),
        const SizedBox(height: 24),
        const _SectionHeader(title: 'Upcoming Tasks'),
        const SizedBox(height: 12),
        _DataList(
          items:
              (data['upcoming_tasks'] as List?)?.cast<Map<String, dynamic>>() ??
              [],
          onTap: (item) => _openDetail(context, 'tasks', item),
          emptyIcon: Icons.task_alt,
          emptyTitle: 'All caught up!',
          emptySubtitle: 'No upcoming tasks to show',
        ),
        const SizedBox(height: 24),
        const _SectionHeader(title: 'Upcoming Handover'),
        const SizedBox(height: 12),
        _DataList(
          items:
              (data['upcoming_handover'] as List?)
                  ?.cast<Map<String, dynamic>>() ??
              [],
          onTap: (item) => _openDetail(context, 'projects', item),
          emptyIcon: Icons.home_work_outlined,
          emptyTitle: 'No handovers scheduled',
          emptySubtitle: 'Upcoming project handovers will appear here',
        ),
        const SizedBox(height: 16),
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
      HapticFeedback.lightImpact();
      Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => DetailScreen(endpoint: endpoint, id: id),
        ),
      );
    }
  }

  void _openScreen(BuildContext context, Widget screen) {
    HapticFeedback.lightImpact();
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
  const _MetricCard({required this.item, required this.index});

  final _MetricItem item;
  final int index;

  @override
  Widget build(BuildContext context) {
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: 1),
      duration: Duration(milliseconds: 300 + (index * 100)),
      curve: Curves.easeOutCubic,
      builder: (context, value, child) {
        return Transform.translate(
          offset: Offset(0, 20 * (1 - value)),
          child: Opacity(opacity: value, child: child),
        );
      },
      child: Material(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: BorderRadius.circular(16),
        child: InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: item.onTap != null
              ? () {
                  HapticFeedback.lightImpact();
                  item.onTap!();
                }
              : null,
          child: Ink(
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(16),
              border: Border.all(
                color: Theme.of(context).colorScheme.outline.withAlpha(100),
              ),
            ),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    width: 38,
                    height: 38,
                    decoration: BoxDecoration(
                      color: item.color.withAlpha(25),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Icon(item.icon, color: item.color, size: 20),
                  ),
                  const Spacer(),
                  Text(
                    item.value,
                    style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    item.label,
                    style: Theme.of(context).textTheme.labelMedium?.copyWith(
                      color: AppTheme.onSurface.withAlpha(140),
                    ),
                  ),
                  if (item.onTap != null) ...[
                    const SizedBox(height: 4),
                    Row(
                      children: [
                        Text(
                          'View all',
                          style: Theme.of(context).textTheme.labelSmall?.copyWith(
                            color: item.color,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        const SizedBox(width: 2),
                        Icon(Icons.arrow_forward, size: 12, color: item.color),
                      ],
                    ),
                  ],
                ],
              ),
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
    final hour = DateTime.now().hour;
    final greeting = hour < 12
        ? 'Good morning'
        : hour < 17
            ? 'Good afternoon'
            : 'Good evening';

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            AppTheme.primary,
            AppTheme.primary.withAlpha(230),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(18),
        boxShadow: [
          BoxShadow(
            color: AppTheme.primary.withAlpha(40),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            greeting,
            style: Theme.of(context).textTheme.labelLarge?.copyWith(
              color: Colors.white.withAlpha(200),
            ),
          ),
          const SizedBox(height: 4),
          Text(
            userName,
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
              color: Colors.white,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
            decoration: BoxDecoration(
              color: Colors.white.withAlpha(25),
              borderRadius: BorderRadius.circular(20),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  Icons.workspace_premium_outlined,
                  size: 14,
                  color: AppTheme.secondary,
                ),
                const SizedBox(width: 6),
                Text(
                  'Workspace active',
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: Colors.white.withAlpha(220),
                  ),
                ),
              ],
            ),
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
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: AppTheme.surfaceVariant,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Text(
              subtitle!,
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                color: AppTheme.onSurface.withAlpha(160),
              ),
            ),
          ),
      ],
    );
  }
}

class _DataList extends StatelessWidget {
  const _DataList({
    required this.items,
    required this.onTap,
    required this.emptyIcon,
    required this.emptyTitle,
    required this.emptySubtitle,
  });

  final List<Map<String, dynamic>> items;
  final void Function(Map<String, dynamic>) onTap;
  final IconData emptyIcon;
  final String emptyTitle;
  final String emptySubtitle;

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) {
      return _EmptyState(
        icon: emptyIcon,
        title: emptyTitle,
        subtitle: emptySubtitle,
      );
    }

    return Column(
      children: items
          .asMap()
          .entries
          .map(
            (entry) => TweenAnimationBuilder<double>(
              tween: Tween(begin: 0, end: 1),
              duration: Duration(milliseconds: 300 + (entry.key * 80)),
              curve: Curves.easeOutCubic,
              builder: (context, value, child) {
                return Transform.translate(
                  offset: Offset(0, 15 * (1 - value)),
                  child: Opacity(opacity: value, child: child),
                );
              },
              child: Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: AppListTile(
                  title: Text(
                    entry.value['title']?.toString() ??
                        entry.value['name']?.toString() ??
                        'Item',
                  ),
                  subtitle: Text(
                    entry.value['status']?.toString() ??
                        entry.value['current_stage']?.toString() ??
                        '',
                  ),
                  trailing: Icon(
                    Icons.chevron_right,
                    color: AppTheme.onSurface.withAlpha(100),
                  ),
                  onTap: () => onTap(entry.value),
                ),
              ),
            ),
          )
          .toList(),
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState({
    required this.icon,
    required this.title,
    required this.subtitle,
  });

  final IconData icon;
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 28, horizontal: 20),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: Theme.of(context).colorScheme.outline.withAlpha(100),
        ),
      ),
      child: Column(
        children: [
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: AppTheme.primary.withAlpha(12),
              borderRadius: BorderRadius.circular(50),
            ),
            child: Icon(
              icon,
              size: 28,
              color: AppTheme.primary.withAlpha(160),
            ),
          ),
          const SizedBox(height: 14),
          Text(
            title,
            style: Theme.of(context).textTheme.titleSmall?.copyWith(
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            subtitle,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: AppTheme.onSurface.withAlpha(120),
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}
