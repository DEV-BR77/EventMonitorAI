import 'dart:async';
import 'dart:math' as math;
import 'dart:typed_data';

import 'package:record/record.dart';

import '../domain/measurement.dart';

class MeasurementService {
  MeasurementService({AudioRecorder? recorder})
    : _recorder = recorder ?? AudioRecorder();

  static const sampleRate = 16000;
  static const _referenceAmplitude = 32768.0;
  static const _floorDb = 20.0;
  static const frequencies = <double>[
    31.5,
    63,
    125,
    250,
    500,
    1000,
    2000,
    4000,
    8000,
  ];

  final AudioRecorder _recorder;
  final _controller = StreamController<MeasurementSnapshot>.broadcast();
  StreamSubscription<Uint8List>? _audioSubscription;
  Timer? _ticker;
  DateTime? _startedAt;
  double _calibrationOffset = 0;
  double? _minimum;
  double? _maximum;
  double _sum = 0;
  int _count = 0;
  MeasurementSnapshot _last = const MeasurementSnapshot.ready();

  Stream<MeasurementSnapshot> get snapshots => _controller.stream;
  MeasurementSnapshot get current => _last;

  Future<void> start({required double calibrationOffset}) async {
    if (_last.isRunning) return;
    if (!await _recorder.hasPermission()) {
      _emit(
        const MeasurementSnapshot(
          status: SessionStatus.error,
          elapsed: Duration.zero,
          error: 'Mikrofonzugriff wurde nicht freigegeben.',
        ),
      );
      return;
    }
    _calibrationOffset = calibrationOffset;
    _minimum = null;
    _maximum = null;
    _sum = 0;
    _count = 0;
    _startedAt = DateTime.now();
    final audio = await _recorder.startStream(
      const RecordConfig(
        encoder: AudioEncoder.pcm16bits,
        sampleRate: sampleRate,
        numChannels: 1,
        autoGain: false,
        echoCancel: false,
        noiseSuppress: false,
      ),
    );
    _audioSubscription = audio.listen(
      _process,
      onError: (Object error) {
        _emit(
          MeasurementSnapshot(
            status: SessionStatus.error,
            elapsed: _elapsed,
            error: 'Messdaten konnten nicht gelesen werden: $error',
          ),
        );
      },
    );
    _ticker = Timer.periodic(const Duration(seconds: 1), (_) => _emit(_last));
  }

  void _process(Uint8List bytes) {
    final samples = <double>[];
    final view = ByteData.sublistView(bytes);
    for (var offset = 0; offset + 1 < bytes.length; offset += 2) {
      samples.add(view.getInt16(offset, Endian.little).toDouble());
    }
    if (samples.isEmpty) return;
    final squareMean =
        samples.fold<double>(0, (sum, value) => sum + value * value) /
        samples.length;
    final rms = math.sqrt(squareMean);
    final unweighted =
        20 * math.log(math.max(1, rms) / _referenceAmplitude) / math.ln10 + 94;
    final level = math.max(_floorDb, unweighted + _calibrationOffset);
    _minimum = math.min(_minimum ?? level, level);
    _maximum = math.max(_maximum ?? level, level);
    _sum += level;
    _count++;
    _emit(
      MeasurementSnapshot(
        status: SessionStatus.running,
        elapsed: _elapsed,
        currentDb: level,
        minimumDb: _minimum,
        maximumDb: _maximum,
        averageDb: _sum / _count,
        spectrum: _bandLevels(samples),
      ),
    );
  }

  List<double> _bandLevels(List<double> samples) {
    final window = samples.length > 512
        ? samples.sublist(samples.length - 512)
        : samples;
    return frequencies
        .map((frequency) {
          var real = 0.0;
          var imaginary = 0.0;
          for (var i = 0; i < window.length; i++) {
            final hann = window.length == 1
                ? 1.0
                : 0.5 * (1 - math.cos(2 * math.pi * i / (window.length - 1)));
            final angle = 2 * math.pi * frequency * i / sampleRate;
            real += window[i] * hann * math.cos(angle);
            imaginary -= window[i] * hann * math.sin(angle);
          }
          final magnitude =
              math.sqrt(real * real + imaginary * imaginary) /
              math.max(1, window.length);
          return (20 * math.log(math.max(1, magnitude)) / math.ln10)
              .clamp(0, 100)
              .toDouble();
        })
        .toList(growable: false);
  }

  Duration get _elapsed => _startedAt == null
      ? Duration.zero
      : DateTime.now().difference(_startedAt!);

  Future<void> stop() async {
    _ticker?.cancel();
    await _audioSubscription?.cancel();
    await _recorder.stop();
    _emit(
      MeasurementSnapshot(
        status: SessionStatus.stopped,
        elapsed: _elapsed,
        currentDb: _last.currentDb,
        minimumDb: _last.minimumDb,
        maximumDb: _last.maximumDb,
        averageDb: _last.averageDb,
        spectrum: _last.spectrum,
      ),
    );
  }

  void _emit(MeasurementSnapshot snapshot) {
    _last = snapshot;
    if (!_controller.isClosed) _controller.add(snapshot);
  }

  Future<void> dispose() async {
    _ticker?.cancel();
    await _audioSubscription?.cancel();
    await _recorder.dispose();
    await _controller.close();
  }
}
