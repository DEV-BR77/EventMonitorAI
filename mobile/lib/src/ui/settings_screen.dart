import 'package:flutter/material.dart';

import '../app_state.dart';

class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key, required this.state});
  final AppState state;

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Einstellungen')),
    body: ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Card(
          child: Column(
            children: [
              ListTile(
                title: Text(state.tenantName ?? 'Kundenbereich'),
                subtitle: Text(
                  'Tenant-ID ${state.tenantId} · ${state.username}',
                ),
                leading: const Icon(Icons.domain),
              ),
              const Divider(height: 1),
              ListTile(
                title: const Text('Messpunkt'),
                subtitle: Text(
                  state.deviceId == null
                      ? 'Dieses Smartphone (noch nicht serverseitig zugeordnet)'
                      : '${state.deviceName} · ${state.deviceId}',
                ),
                leading: const Icon(Icons.sensors),
                onTap: () => _selectDevice(context),
              ),
            ],
          ),
        ),
        const SizedBox(height: 12),
        Card(
          child: Column(
            children: [
              ListTile(
                title: const Text('Kalibrierkorrektur'),
                subtitle: Text(
                  '${state.calibrationOffset >= 0 ? '+' : ''}${state.calibrationOffset.toStringAsFixed(1)} dB · lokale Geräteabweichung',
                ),
                leading: const Icon(Icons.tune),
              ),
              Slider(
                value: state.calibrationOffset,
                min: -20,
                max: 20,
                divisions: 80,
                label: '${state.calibrationOffset.toStringAsFixed(1)} dB',
                onChanged: state.setCalibration,
              ),
              const Padding(
                padding: EdgeInsets.fromLTRB(16, 0, 16, 16),
                child: Text(
                  'Der Offset muss durch Vergleich mit einem geeigneten Referenzmessgerät dokumentiert werden. Smartphone-Werte sind keine geeichte Messung.',
                  style: TextStyle(color: Colors.white60, fontSize: 12),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 12),
        const Card(
          child: ListTile(
            leading: Icon(Icons.privacy_tip_outlined),
            title: Text('Datenschutzstatus'),
            subtitle: Text(
              'Lokale Analyse · keine Audioübertragung im Prototyp · sichtbare Vordergrundsitzung · Berechtigung jederzeit im System widerrufbar',
            ),
          ),
        ),
        const SizedBox(height: 20),
        OutlinedButton.icon(
          onPressed: state.logout,
          icon: const Icon(Icons.logout),
          label: const Text('Abmelden und lokale Zugangsdaten löschen'),
        ),
      ],
    ),
  );

  Future<void> _selectDevice(BuildContext context) async {
    if (state.availableDevices.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Keine zuordenbaren Geräte in diesem Kundenbereich.'),
        ),
      );
      return;
    }
    await showModalBottomSheet<void>(
      context: context,
      builder: (context) => SafeArea(
        child: ListView(
          shrinkWrap: true,
          children: [
            const ListTile(
              title: Text('Messpunkt auswählen'),
              subtitle: Text(
                'Es werden ausschließlich Geräte des angemeldeten Kundenbereichs angezeigt.',
              ),
            ),
            ...state.availableDevices.map(
              (device) => ListTile(
                leading: const Icon(Icons.sensors),
                title: Text('${device['name']}'),
                subtitle: Text('${device['device_id']}'),
                onTap: () async {
                  await state.selectDevice(
                    '${device['device_id']}',
                    '${device['name']}',
                  );
                  if (context.mounted) Navigator.pop(context);
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}
