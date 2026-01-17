import 'package:flutter/material.dart';

import '../dashboard/dashboard_screen.dart';
import '../modules/modules_screen.dart';
import '../projects/projects_list_screen.dart';
import '../tasks/tasks_list_screen.dart';

class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _currentIndex = 0;

  late final List<Widget> _pages = [
    const DashboardScreen(),
    const ProjectsListScreen(),
    const TasksListScreen(),
    ModulesScreen.finance(),
    ModulesScreen.more(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(index: _currentIndex, children: _pages),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _currentIndex,
        onDestinationSelected: (index) => setState(() => _currentIndex = index),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.dashboard_outlined),
            label: 'Dashboard',
          ),
          NavigationDestination(
            icon: Icon(Icons.apartment_outlined),
            label: 'Projects',
          ),
          NavigationDestination(
            icon: Icon(Icons.check_circle_outline),
            label: 'Tasks',
          ),
          NavigationDestination(
            icon: Icon(Icons.account_balance_outlined),
            label: 'Finance',
          ),
          NavigationDestination(icon: Icon(Icons.menu), label: 'More'),
        ],
      ),
    );
  }
}
