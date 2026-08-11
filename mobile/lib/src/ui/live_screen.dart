import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../app_state.dart';
import '../domain/measurement.dart';
import '../services/measurement_service.dart';

class LiveScreen extends StatefulWidget {
  const LiveScreen({super.key, required this.state});
  final AppState state;

  @override
  State<LiveScreen> createState() => _LiveScreenState();
}

class _LiveScreenState extends State<LiveScreen> with WidgetsBindingObserver {
  late MeasurementSnapshot snapshot = widget.state.measurement.current;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    widget.state.measurement.snapshots.listen((value) {
      if (mounted) setState(() => snapshot = value);
    });
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state != AppLifecycleState.resumed && snapshot.isRunning) {
      widget.state.measurement.stop();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Messung beendet: Die erste Version misst nur sichtbar im Vordergrund.',
            ),
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(widget.state.deviceName, style: const TextStyle(fontSize: 18)),
          Text(
            snapshot.isRunning ? '● Mikrofon aktiv · lokal' : '○ Sensor bereit',
            style: TextStyle(
              fontSize: 12,
              color: snapshot.isRunning
                  ? const Color(0xff31d0aa)
                  : Colors.white60,
            ),
          ),
        ],
      ),
      actions: const [
        Padding(
          padding: EdgeInsets.only(right: 16),
          child: Center(child: Text('dB(A)')),
        ),
      ],
    ),
    body: SafeArea(
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
        children: [
          if (snapshot.isRunning)
            Semantics(
              liveRegion: true,
              child: MaterialBanner(
                content: Text('Messsitzung aktiv · Mikrofon wird verwendet'),
                leading: Icon(Icons.mic, color: Color(0xff31d0aa)),
                actions: [SizedBox.shrink()],
              ),
            ),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                children: [
                  const Text(
                    'Aktueller Schallpegel',
                    style: TextStyle(color: Colors.white60),
                  ),
                  const SizedBox(height: 8),
                  Semantics(
                    label: snapshot.currentDb == null
                        ? 'Kein Messwert'
                        : '${snapshot.currentDb!.toStringAsFixed(1)} Dezibel A',
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        Text(
                          _value(snapshot.currentDb),
                          style: const TextStyle(
                            fontSize: 72,
                            fontWeight: FontWeight.w300,
                            height: 1,
                          ),
                        ),
                        const Padding(
                          padding: EdgeInsets.only(bottom: 8),
                          child: Text(' dB(A)', style: TextStyle(fontSize: 18)),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 18),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceAround,
                    children: [
                      _Metric(label: 'MIN', value: _value(snapshot.minimumDb)),
                      _Metric(label: 'MAX', value: _value(snapshot.maximumDb)),
                      _Metric(label: 'AVG', value: _value(snapshot.averageDb)),
                    ],
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Frequenzspektrum',
                    style: TextStyle(fontWeight: FontWeight.w600),
                  ),
                  const SizedBox(height: 16),
                  SizedBox(
                    height: 142,
                    child: snapshot.spectrum.isEmpty
                        ? const Center(
                            child: Text(
                              'Starten Sie eine Messung für Spektraldaten.',
                              style: TextStyle(color: Colors.white54),
                            ),
                          )
                        : Row(
                            crossAxisAlignment: CrossAxisAlignment.end,
                            children: List.generate(snapshot.spectrum.length, (
                              index,
                            ) {
                              final height = math.max(
                                4,
                                snapshot.spectrum[index] / 100 * 100,
                              );
                              final frequency =
                                  MeasurementService.frequencies[index];
                              return Expanded(
                                child: Column(
                                  mainAxisAlignment: MainAxisAlignment.end,
                                  children: [
                                    Container(
                                      height: height.toDouble(),
                                      margin: const EdgeInsets.symmetric(
                                        horizontal: 2,
                                      ),
                                      decoration: BoxDecoration(
                                        color: const Color(0xff31d0aa),
                                        borderRadius: BorderRadius.circular(3),
                                      ),
                                    ),
                                    const SizedBox(height: 6),
                                    Text(
                                      frequency >= 1000
                                          ? '${frequency ~/ 1000}k'
                                          : '${frequency.round()}',
                                      style: const TextStyle(
                                        fontSize: 10,
                                        color: Colors.white54,
                                      ),
                                    ),
                                  ],
                                ),
                              );
                            }),
                          ),
                  ),
                  const Align(
                    alignment: Alignment.centerRight,
                    child: Text(
                      'Hz',
                      style: TextStyle(fontSize: 11, color: Colors.white54),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
          _AiCard(
            event: widget.state.events.isEmpty
                ? null
                : widget.state.events.first,
          ),
          const SizedBox(height: 20),
          Text(
            _duration(snapshot.elapsed),
            textAlign: TextAlign.center,
            style: const TextStyle(
              fontFeatures: [FontFeature.tabularFigures()],
              color: Colors.white70,
            ),
          ),
          const SizedBox(height: 8),
          SizedBox(
            height: 64,
            child: FilledButton.icon(
              style: FilledButton.styleFrom(
                backgroundColor: snapshot.isRunning
                    ? const Color(0xffd64b5f)
                    : const Color(0xff31d0aa),
                foregroundColor: const Color(0xff07130f),
              ),
              onPressed: _toggle,
              icon: Icon(
                snapshot.isRunning ? Icons.stop_rounded : Icons.mic_rounded,
              ),
              label: Text(
                snapshot.isRunning
                    ? 'Messsitzung beenden'
                    : 'Messsitzung starten',
              ),
            ),
          ),
          if (snapshot.error != null)
            Padding(
              padding: const EdgeInsets.only(top: 12),
              child: Text(
                snapshot.error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
                textAlign: TextAlign.center,
              ),
            ),
          const SizedBox(height: 12),
          const Text(
            'Smartphone-Messwerte sind orientierend und ohne dokumentierte Vergleichskalibrierung nicht einer Referenzmessstelle gleichzusetzen.',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 12, color: Colors.white54),
          ),
        ],
      ),
    ),
  );

  Future<void> _toggle() async {
    if (snapshot.isRunning) {
      final stop = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Messsitzung beenden?'),
          content: const Text(
            'Die laufende Protokollierung wird beendet. Die Zusammenfassung bleibt sichtbar.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Weiter messen'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Beenden'),
            ),
          ],
        ),
      );
      if (stop == true) await widget.state.measurement.stop();
      return;
    }
    if (!widget.state.privacyAccepted) {
      final accepted = await showDialog<bool>(
        context: context,
        barrierDismissible: false,
        builder: (context) => AlertDialog(
          title: const Text('Mikrofon und Datenschutz'),
          content: const Text(
            'Die App analysiert Pegel und Frequenz lokal, nur während einer sichtbar gestarteten Sitzung. In diesem Prototyp werden keine Audiodaten hochgeladen. Beim Wechsel in den Hintergrund endet die Messung.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Abbrechen'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Verstanden und starten'),
            ),
          ],
        ),
      );
      if (accepted != true) return;
      await widget.state.acceptPrivacy();
    }
    await widget.state.measurement.start(
      calibrationOffset: widget.state.calibrationOffset,
    );
  }

  String _value(double? value) =>
      value == null ? '—' : value.toStringAsFixed(1);
  String _duration(Duration value) =>
      '${value.inHours.toString().padLeft(2, '0')}:${(value.inMinutes % 60).toString().padLeft(2, '0')}:${(value.inSeconds % 60).toString().padLeft(2, '0')}';

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }
}

class _Metric extends StatelessWidget {
  const _Metric({required this.label, required this.value});
  final String label;
  final String value;
  @override
  Widget build(BuildContext context) => Column(
    children: [
      Text(label, style: const TextStyle(color: Colors.white54, fontSize: 12)),
      Text(
        value,
        style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w600),
      ),
    ],
  );
}

class _AiCard extends StatelessWidget {
  const _AiCard({required this.event});
  final MobileEvent? event;
  @override
  Widget build(BuildContext context) => Card(
    child: ListTile(
      leading: const Icon(Icons.auto_awesome, color: Color(0xffffc857)),
      title: Text(event == null ? 'Kein aktueller KI-Vorschlag' : event!.label),
      subtitle: Text(
        event == null
            ? 'Erkannte Ereignisse erscheinen hier.'
            : 'KI-Vorschlag · ${(event!.confidence * 100).round()} % · ${event!.status}',
      ),
      trailing: event == null ? null : const Icon(Icons.chevron_right),
    ),
  );
}
