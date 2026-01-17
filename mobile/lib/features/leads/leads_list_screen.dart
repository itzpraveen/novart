import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/di/providers.dart';
import '../common/app_list_tile.dart';
import 'lead_detail_screen.dart';
import 'lead_form_screen.dart';

class LeadQuery {
  LeadQuery(this.search, this.status);

  final String search;
  final String status;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is LeadQuery && search == other.search && status == other.status;

  @override
  int get hashCode => Object.hash(search, status);
}

final leadsProvider =
    FutureProvider.family<List<Map<String, dynamic>>, LeadQuery>((
      ref,
      query,
    ) async {
      final repo = ref.watch(apiRepositoryProvider);
      final params = <String, dynamic>{};
      if (query.search.isNotEmpty) {
        params['search'] = query.search;
      }
      if (query.status.isNotEmpty) {
        params['status'] = query.status;
      }
      return repo.fetchList('leads', params: params.isEmpty ? null : params);
    });

class LeadsListScreen extends ConsumerStatefulWidget {
  const LeadsListScreen({super.key});

  @override
  ConsumerState<LeadsListScreen> createState() => _LeadsListScreenState();
}

class _LeadsListScreenState extends ConsumerState<LeadsListScreen> {
  String _search = '';
  String _status = '';

  @override
  Widget build(BuildContext context) {
    final asyncLeads = ref.watch(leadsProvider(LeadQuery(_search, _status)));
    final role = ref.watch(authControllerProvider).session?.user.role ?? '';
    final canCreate = role == 'admin' || role == 'architect';

    return Scaffold(
      appBar: AppBar(title: const Text('Leads')),
      floatingActionButton: canCreate
          ? FloatingActionButton(
              onPressed: () async {
                final created = await Navigator.of(context)
                    .push<Map<String, dynamic>>(
                      MaterialPageRoute(builder: (_) => const LeadFormScreen()),
                    );
                if (created != null) {
                  ref.invalidate(leadsProvider(LeadQuery(_search, _status)));
                }
              },
              child: const Icon(Icons.add),
            )
          : null,
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              children: [
                TextField(
                  decoration: const InputDecoration(
                    hintText: 'Search leads...',
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
                    DropdownMenuItem(value: '', child: Text('All')),
                    DropdownMenuItem(value: 'new', child: Text('New')),
                    DropdownMenuItem(
                      value: 'discussion',
                      child: Text('In Discussion'),
                    ),
                    DropdownMenuItem(value: 'won', child: Text('Won')),
                    DropdownMenuItem(value: 'lost', child: Text('Lost')),
                  ],
                  onChanged: (value) => setState(() => _status = value ?? ''),
                ),
              ],
            ),
          ),
          Expanded(
            child: asyncLeads.when(
              data: (leads) {
                if (leads.isEmpty) {
                  return const Center(child: Text('No leads found.'));
                }
                return RefreshIndicator(
                  onRefresh: () async => ref.invalidate(
                    leadsProvider(LeadQuery(_search, _status)),
                  ),
                  child: ListView.separated(
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    itemBuilder: (context, index) {
                      final lead = leads[index];
                      return AppListTile(
                        title: Text(lead['title']?.toString() ?? 'Lead'),
                        subtitle: Text(
                          '${lead['client_detail']?['name'] ?? 'Client'} • ${lead['status'] ?? ''}',
                        ),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () {
                          final id = lead['id'];
                          if (id is int) {
                            Navigator.of(context).push(
                              MaterialPageRoute(
                                builder: (_) => LeadDetailScreen(leadId: id),
                              ),
                            );
                          }
                        },
                      );
                    },
                    separatorBuilder: (context, index) =>
                        const SizedBox(height: 12),
                    itemCount: leads.length,
                  ),
                );
              },
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (error, _) =>
                  Center(child: Text('Failed to load leads: $error')),
            ),
          ),
        ],
      ),
    );
  }
}
