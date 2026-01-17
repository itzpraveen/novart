import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/di/providers.dart';
import '../clients/clients_list_screen.dart';
import '../documents/documents_list_screen.dart';
import '../leads/leads_list_screen.dart';
import '../site_issues/site_issues_list_screen.dart';
import '../site_visits/site_visits_list_screen.dart';
import 'simple_list_screen.dart';

class ModuleItem {
  const ModuleItem({
    required this.title,
    required this.endpoint,
    required this.icon,
    this.permissionKey,
    this.builder,
  });

  final String title;
  final String endpoint;
  final IconData icon;
  final String? permissionKey;
  final WidgetBuilder? builder;
}

class ModulesScreen extends ConsumerWidget {
  const ModulesScreen._({
    required this.title,
    required this.modules,
    this.showSignOut = false,
  });

  final String title;
  final List<ModuleItem> modules;
  final bool showSignOut;

  factory ModulesScreen.finance() {
    return ModulesScreen._(
      title: 'Finance',
      modules: [
        ModuleItem(
          title: 'Invoices',
          endpoint: 'invoices',
          icon: Icons.receipt_long,
          permissionKey: 'invoices',
        ),
        ModuleItem(
          title: 'Payments',
          endpoint: 'payments',
          icon: Icons.payments_outlined,
          permissionKey: 'invoices',
        ),
        ModuleItem(
          title: 'Receipts',
          endpoint: 'receipts',
          icon: Icons.receipt_outlined,
          permissionKey: 'invoices',
        ),
        ModuleItem(
          title: 'Bills',
          endpoint: 'bills',
          icon: Icons.request_quote_outlined,
          permissionKey: 'finance',
        ),
        ModuleItem(
          title: 'Bill Payments',
          endpoint: 'bill-payments',
          icon: Icons.payment_outlined,
          permissionKey: 'finance',
        ),
        ModuleItem(
          title: 'Accounts',
          endpoint: 'accounts',
          icon: Icons.account_balance_outlined,
          permissionKey: 'finance',
        ),
        ModuleItem(
          title: 'Transactions',
          endpoint: 'transactions',
          icon: Icons.sync_alt,
          permissionKey: 'finance',
        ),
        ModuleItem(
          title: 'Client Advances',
          endpoint: 'client-advances',
          icon: Icons.account_balance_wallet_outlined,
          permissionKey: 'finance',
        ),
        ModuleItem(
          title: 'Advance Allocations',
          endpoint: 'client-advance-allocations',
          icon: Icons.move_up_outlined,
          permissionKey: 'finance',
        ),
        ModuleItem(
          title: 'Expense Claims',
          endpoint: 'expense-claims',
          icon: Icons.receipt_long_outlined,
          permissionKey: 'finance',
        ),
        ModuleItem(
          title: 'Claim Payments',
          endpoint: 'expense-claim-payments',
          icon: Icons.payments,
          permissionKey: 'finance',
        ),
        ModuleItem(
          title: 'Recurring Rules',
          endpoint: 'recurring-rules',
          icon: Icons.repeat,
          permissionKey: 'finance',
        ),
        ModuleItem(
          title: 'Bank Statements',
          endpoint: 'bank-statements',
          icon: Icons.account_balance,
          permissionKey: 'finance',
        ),
      ],
    );
  }

  factory ModulesScreen.more() {
    return ModulesScreen._(
      title: 'More',
      modules: [
        ModuleItem(
          title: 'Clients',
          endpoint: 'clients',
          icon: Icons.people_outline,
          permissionKey: 'clients',
          builder: (context) => const ClientsListScreen(),
        ),
        ModuleItem(
          title: 'Leads',
          endpoint: 'leads',
          icon: Icons.filter_alt_outlined,
          permissionKey: 'leads',
          builder: (context) => const LeadsListScreen(),
        ),
        ModuleItem(
          title: 'Site Visits',
          endpoint: 'site-visits',
          icon: Icons.location_on_outlined,
          permissionKey: 'site_visits',
          builder: (context) => const SiteVisitsListScreen(),
        ),
        ModuleItem(
          title: 'Site Issues',
          endpoint: 'site-issues',
          icon: Icons.report_problem_outlined,
          permissionKey: 'site_visits',
          builder: (context) => const SiteIssuesListScreen(),
        ),
        ModuleItem(
          title: 'Documents',
          endpoint: 'documents',
          icon: Icons.folder_copy_outlined,
          permissionKey: 'docs',
          builder: (context) => const DocumentsListScreen(),
        ),
        ModuleItem(
          title: 'Team',
          endpoint: 'team',
          icon: Icons.groups_outlined,
          permissionKey: 'team',
        ),
        ModuleItem(
          title: 'Users',
          endpoint: 'users',
          icon: Icons.admin_panel_settings_outlined,
          permissionKey: 'users',
        ),
        ModuleItem(
          title: 'Notifications',
          endpoint: 'notifications',
          icon: Icons.notifications_outlined,
        ),
        ModuleItem(
          title: 'Firm Profiles',
          endpoint: 'firm-profiles',
          icon: Icons.apartment_outlined,
          permissionKey: 'settings',
        ),
        ModuleItem(
          title: 'Role Permissions',
          endpoint: 'role-permissions',
          icon: Icons.lock_outline,
          permissionKey: 'settings',
        ),
        ModuleItem(
          title: 'Reminder Settings',
          endpoint: 'reminder-settings',
          icon: Icons.notifications_active_outlined,
          permissionKey: 'settings',
        ),
        ModuleItem(
          title: 'WhatsApp Configs',
          endpoint: 'whatsapp-configs',
          icon: Icons.chat_bubble_outline,
          permissionKey: 'settings',
        ),
        ModuleItem(
          title: 'Project Milestones',
          endpoint: 'project-milestones',
          icon: Icons.flag_outlined,
          permissionKey: 'finance',
        ),
      ],
      showSignOut: true,
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final permissions =
        ref.watch(authControllerProvider).session?.permissions ?? {};
    final visibleModules = modules.where((module) {
      final key = module.permissionKey;
      if (key == null) {
        return true;
      }
      return permissions[key] == true;
    }).toList();

    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          ...visibleModules.map(
            (module) => Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: ListTile(
                tileColor: Theme.of(context).colorScheme.surface,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
                leading: Icon(
                  module.icon,
                  color: Theme.of(context).colorScheme.primary,
                ),
                title: Text(module.title),
                trailing: const Icon(Icons.chevron_right),
                onTap: () {
                  final builder = module.builder;
                  Navigator.of(context).push(
                    MaterialPageRoute(
                      builder:
                          builder ??
                          (_) => SimpleListScreen(
                            title: module.title,
                            endpoint: module.endpoint,
                          ),
                    ),
                  );
                },
              ),
            ),
          ),
          if (showSignOut)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: ListTile(
                tileColor: Colors.white,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
                leading: const Icon(Icons.logout),
                title: const Text('Sign out'),
                onTap: () =>
                    ref.read(authControllerProvider.notifier).signOut(),
              ),
            ),
        ],
      ),
    );
  }
}
