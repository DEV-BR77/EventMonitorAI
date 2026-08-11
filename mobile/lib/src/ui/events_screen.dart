import 'package:flutter/material.dart';

import '../app_state.dart';

class EventsScreen extends StatelessWidget {
  const EventsScreen({super.key, required this.state});
  final AppState state;

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Ereignisse'),
      actions: [
        IconButton(
          onPressed: state.refresh,
          icon: const Icon(Icons.refresh),
          tooltip: 'Aktualisieren',
        ),
      ],
    ),
    body: state.events.isEmpty
        ? const Center(child: Text('Keine Ereignisse in diesem Kundenbereich.'))
        : RefreshIndicator(
            onRefresh: state.refresh,
            child: ListView.separated(
              padding: const EdgeInsets.all(16),
              itemCount: state.events.length,
              separatorBuilder: (_, _) => const SizedBox(height: 8),
              itemBuilder: (context, index) {
                final event = state.events[index];
                return Card(
                  child: ListTile(
                    leading: CircleAvatar(
                      child: Text('${event.dbLevel.round()}'),
                    ),
                    title: Text(event.label),
                    subtitle: Text(
                      '${event.timestamp.toLocal()}\nKI-Vorschlag ${(event.confidence * 100).round()} % · ${event.status}',
                    ),
                    isThreeLine: true,
                    trailing: const Icon(Icons.chevron_right),
                  ),
                );
              },
            ),
          ),
  );
}
