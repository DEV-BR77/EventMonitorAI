import 'package:flutter/material.dart';

import '../app_state.dart';
import 'events_screen.dart';
import 'live_screen.dart';
import 'log_screen.dart';
import 'settings_screen.dart';

class HomeShell extends StatefulWidget {
  const HomeShell({super.key, required this.state});
  final AppState state;

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int index = 0;

  @override
  Widget build(BuildContext context) {
    final pages = [
      LiveScreen(state: widget.state),
      EventsScreen(state: widget.state),
      LogScreen(state: widget.state),
      const _Placeholder(title: 'Auswertung', icon: Icons.query_stats),
      SettingsScreen(state: widget.state),
    ];
    return Scaffold(
      body: IndexedStack(index: index, children: pages),
      bottomNavigationBar: NavigationBar(
        selectedIndex: index,
        onDestinationSelected: (value) => setState(() => index = value),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.graphic_eq), label: 'Live'),
          NavigationDestination(
            icon: Icon(Icons.event_note),
            label: 'Ereignisse',
          ),
          NavigationDestination(icon: Icon(Icons.receipt_long), label: 'ELM'),
          NavigationDestination(
            icon: Icon(Icons.query_stats),
            label: 'Auswertung',
          ),
          NavigationDestination(
            icon: Icon(Icons.settings),
            label: 'Einstellungen',
          ),
        ],
      ),
    );
  }
}

class _Placeholder extends StatelessWidget {
  const _Placeholder({required this.title, required this.icon});
  final String title;
  final IconData icon;
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: Text(title)),
    body: Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 56, color: Colors.white38),
          const SizedBox(height: 12),
          const Text('Wird im nächsten Ausbauschritt ergänzt.'),
        ],
      ),
    ),
  );
}
