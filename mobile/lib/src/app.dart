import 'package:flutter/material.dart';

import 'app_state.dart';
import 'ui/home_shell.dart';
import 'ui/login_screen.dart';

class EventMonitorApp extends StatefulWidget {
  const EventMonitorApp({super.key});

  @override
  State<EventMonitorApp> createState() => _EventMonitorAppState();
}

class _EventMonitorAppState extends State<EventMonitorApp> {
  final state = AppState();
  late final Future<void> restored = state.restore();

  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'EventMonitor Voice',
    debugShowCheckedModeBanner: false,
    themeMode: ThemeMode.dark,
    darkTheme: ThemeData(
      brightness: Brightness.dark,
      colorScheme: ColorScheme.fromSeed(
        seedColor: const Color(0xff31d0aa),
        brightness: Brightness.dark,
      ),
      scaffoldBackgroundColor: const Color(0xff0d1117),
      cardTheme: const CardThemeData(
        color: Color(0xff151b23),
        margin: EdgeInsets.zero,
      ),
      useMaterial3: true,
    ),
    home: FutureBuilder<void>(
      future: restored,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Scaffold(
            body: Center(child: CircularProgressIndicator()),
          );
        }
        return ListenableBuilder(
          listenable: state,
          builder: (context, _) => state.isAuthenticated
              ? HomeShell(state: state)
              : LoginScreen(state: state),
        );
      },
    ),
  );

  @override
  void dispose() {
    state.dispose();
    super.dispose();
  }
}
