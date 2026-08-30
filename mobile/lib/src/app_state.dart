import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'domain/measurement.dart';
import 'services/api_client.dart';
import 'services/measurement_service.dart';

class AppState extends ChangeNotifier {
  AppState({
    ApiClient? api,
    MeasurementService? measurement,
    FlutterSecureStorage? storage,
  }) : api = api ?? ApiClient(),
       measurement = measurement ?? MeasurementService(),
       storage = storage ?? const FlutterSecureStorage();

  final ApiClient api;
  final MeasurementService measurement;
  final FlutterSecureStorage storage;

  String? baseUrl;
  String? token;
  String? username;
  int? tenantId;
  String? tenantName;
  String? deviceId;
  String deviceName = 'Dieses Smartphone';
  double calibrationOffset = 0;
  bool privacyAccepted = false;
  bool loading = false;
  String? error;
  List<Map<String, dynamic>> availableDevices = const [];
  List<MobileEvent> events = const [];
  List<Map<String, dynamic>> noiseLog = const [];

  bool get isAuthenticated => token != null;

  Future<void> restore() async {
    baseUrl = await storage.read(key: 'base_url');
    token = await storage.read(key: 'access_token');
    username = await storage.read(key: 'username');
    tenantName = await storage.read(key: 'tenant_name');
    tenantId = int.tryParse(await storage.read(key: 'tenant_id') ?? '');
    deviceId = await storage.read(key: 'device_id');
    calibrationOffset =
        double.tryParse(await storage.read(key: 'calibration_offset') ?? '') ??
        0;
    privacyAccepted = await storage.read(key: 'privacy_accepted') == 'true';
    notifyListeners();
  }

  Future<bool> login(String url, String name, String password) async {
    loading = true;
    error = null;
    notifyListeners();
    try {
      final result = await api.login(url, name, password);
      baseUrl = url;
      token = result.token;
      username = result.username;
      tenantId = result.tenantId;
      tenantName = result.tenantName;
      await Future.wait([
        storage.write(key: 'base_url', value: url),
        storage.write(key: 'access_token', value: token),
        storage.write(key: 'username', value: username),
        storage.write(key: 'tenant_id', value: '$tenantId'),
        storage.write(key: 'tenant_name', value: tenantName),
      ]);
      await refresh();
      return true;
    } catch (exception) {
      error = exception.toString();
      return false;
    } finally {
      loading = false;
      notifyListeners();
    }
  }

  Future<void> refresh() async {
    if (baseUrl == null || token == null) return;
    final values = await Future.wait([
      api.devices(baseUrl!, token!),
      api.events(baseUrl!, token!),
      api.noiseLog(baseUrl!, token!),
    ]);
    availableDevices = values[0] as List<Map<String, dynamic>>;
    events = values[1] as List<MobileEvent>;
    noiseLog = values[2] as List<Map<String, dynamic>>;
    notifyListeners();
  }

  Future<void> acceptPrivacy() async {
    privacyAccepted = true;
    await storage.write(key: 'privacy_accepted', value: 'true');
    notifyListeners();
  }

  Future<void> selectDevice(String id, String name) async {
    deviceId = id;
    deviceName = name;
    await storage.write(key: 'device_id', value: id);
    notifyListeners();
  }

  Future<void> setCalibration(double offset) async {
    calibrationOffset = offset.clamp(-30, 30);
    await storage.write(key: 'calibration_offset', value: '$calibrationOffset');
    notifyListeners();
  }

  Future<void> logout() async {
    await measurement.stop();
    await storage.deleteAll();
    token = null;
    tenantId = null;
    tenantName = null;
    username = null;
    deviceId = null;
    privacyAccepted = false;
    notifyListeners();
  }

  @override
  void dispose() {
    api.close();
    measurement.dispose();
    super.dispose();
  }
}
