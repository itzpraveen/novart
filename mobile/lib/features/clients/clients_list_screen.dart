import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/di/providers.dart';
import '../common/app_list_tile.dart';
import 'client_detail_screen.dart';
import 'client_form_screen.dart';

class ClientQuery {
  ClientQuery(this.search);

  final String search;

  @override
  bool operator ==(Object other) =>
      identical(this, other) || other is ClientQuery && other.search == search;

  @override
  int get hashCode => search.hashCode;
}

final clientsProvider =
    FutureProvider.family<List<Map<String, dynamic>>, ClientQuery>((
      ref,
      query,
    ) async {
      final repo = ref.watch(apiRepositoryProvider);
      final params = <String, dynamic>{};
      if (query.search.isNotEmpty) {
        params['search'] = query.search;
      }
      return repo.fetchList('clients', params: params.isEmpty ? null : params);
    });

class ClientsListScreen extends ConsumerStatefulWidget {
  const ClientsListScreen({super.key});

  @override
  ConsumerState<ClientsListScreen> createState() => _ClientsListScreenState();
}

class _ClientsListScreenState extends ConsumerState<ClientsListScreen> {
  String _search = '';

  @override
  Widget build(BuildContext context) {
    final asyncClients = ref.watch(clientsProvider(ClientQuery(_search)));
    final permissions =
        ref.watch(authControllerProvider).session?.permissions ?? {};
    final canCreate = permissions['clients'] == true;

    return Scaffold(
      appBar: AppBar(title: const Text('Clients')),
      floatingActionButton: canCreate
          ? FloatingActionButton(
              onPressed: () async {
                final created = await Navigator.of(context)
                    .push<Map<String, dynamic>>(
                      MaterialPageRoute(
                        builder: (_) => const ClientFormScreen(),
                      ),
                    );
                if (created != null) {
                  ref.invalidate(clientsProvider(ClientQuery(_search)));
                }
              },
              child: const Icon(Icons.add),
            )
          : null,
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: TextField(
              decoration: const InputDecoration(
                hintText: 'Search clients...',
                prefixIcon: Icon(Icons.search),
              ),
              onChanged: (value) => setState(() => _search = value.trim()),
            ),
          ),
          Expanded(
            child: asyncClients.when(
              data: (clients) {
                if (clients.isEmpty) {
                  return const Center(child: Text('No clients found.'));
                }
                return RefreshIndicator(
                  onRefresh: () async {
                    ref.invalidate(clientsProvider(ClientQuery(_search)));
                  },
                  child: ListView.separated(
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    itemBuilder: (context, index) {
                      final client = clients[index];
                      return AppListTile(
                        title: Text(client['name']?.toString() ?? 'Client'),
                        subtitle: Text(
                          client['phone']?.toString() ??
                              client['email']?.toString() ??
                              '',
                        ),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () {
                          final id = client['id'];
                          if (id is int) {
                            Navigator.of(context).push(
                              MaterialPageRoute(
                                builder: (_) =>
                                    ClientDetailScreen(clientId: id),
                              ),
                            );
                          }
                        },
                      );
                    },
                    separatorBuilder: (context, index) =>
                        const SizedBox(height: 12),
                    itemCount: clients.length,
                  ),
                );
              },
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (error, _) =>
                  Center(child: Text('Failed to load clients: $error')),
            ),
          ),
        ],
      ),
    );
  }
}
