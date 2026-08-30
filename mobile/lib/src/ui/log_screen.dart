import 'package:flutter/material.dart';

import '../app_state.dart';

class LogScreen extends StatelessWidget {
  const LogScreen({super.key, required this.state});
  final AppState state;

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('ELM-/Lärmprotokoll'),
      actions: [
        IconButton(
          onPressed: state.refresh,
          icon: const Icon(Icons.refresh),
          tooltip: 'Aktualisieren',
        ),
      ],
    ),
    body: state.noiseLog.isEmpty
        ? const Center(child: Text('Noch keine Protokolleinträge vorhanden.'))
        : ListView.separated(
            padding: const EdgeInsets.all(16),
            itemCount: state.noiseLog.length,
            separatorBuilder: (_, _) => const Divider(),
            itemBuilder: (context, index) {
              final item = state.noiseLog[index];
              return ListTile(
                leading: const Icon(Icons.receipt_long),
                title: Text(
                  '${item['label_de'] ?? item['label'] ?? 'Ereignis'}',
                ),
                subtitle: Text(
                  '${item['timestamp'] ?? ''} · ${item['device'] ?? ''}',
                ),
                trailing: Text('${item['db_level'] ?? '—'} dB(A)'),
              );
            },
          ),
  );
}
