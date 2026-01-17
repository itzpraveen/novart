import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/di/providers.dart';
import '../dashboard/dashboard_screen.dart';
import '../modules/modules_screen.dart';
import '../projects/projects_list_screen.dart';
import '../tasks/tasks_list_screen.dart';
import '../transactions/transactions_screen.dart';

class HomeShell extends ConsumerStatefulWidget {
  const HomeShell({super.key});

  @override
  ConsumerState<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends ConsumerState<HomeShell> {
  int _currentIndex = 0;

  @override
  Widget build(BuildContext context) {
    final session = ref.watch(authControllerProvider).session;
    final role = session?.user.role ?? '';
    final isAdmin = role == 'admin';
    final permissions = session?.permissions ?? {};
    final showCashbook = permissions['finance'] == true || isAdmin;
    final pages = <Widget>[
      const DashboardScreen(),
      const ProjectsListScreen(),
      const TasksListScreen(),
      if (showCashbook) const TransactionsScreen(),
      ModulesScreen.finance(),
      ModulesScreen.more(),
    ];
    final destinations = <NavigationDestination>[
      const NavigationDestination(
        icon: Icon(Icons.dashboard_outlined),
        label: 'Dashboard',
      ),
      const NavigationDestination(
        icon: Icon(Icons.apartment_outlined),
        label: 'Projects',
      ),
      const NavigationDestination(
        icon: Icon(Icons.check_circle_outline),
        label: 'Tasks',
      ),
      if (showCashbook)
        const NavigationDestination(
          icon: Icon(Icons.account_balance_wallet_outlined),
          label: 'Cashbook',
        ),
      const NavigationDestination(
        icon: Icon(Icons.account_balance_outlined),
        label: 'Finance',
      ),
      const NavigationDestination(icon: Icon(Icons.menu), label: 'More'),
    ];
    final safeIndex = _currentIndex >= pages.length ? 0 : _currentIndex;

    return Scaffold(
      body: IndexedStack(index: safeIndex, children: pages),
      bottomNavigationBar: NavigationBar(
        selectedIndex: safeIndex,
        onDestinationSelected: (index) => setState(() => _currentIndex = index),
        destinations: destinations,
      ),
    );
  }
}
