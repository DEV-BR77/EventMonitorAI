enum SessionStatus { ready, running, stopped, error }

class MeasurementSnapshot {
  const MeasurementSnapshot({
    required this.status,
    required this.elapsed,
    this.currentDb,
    this.minimumDb,
    this.maximumDb,
    this.averageDb,
    this.spectrum = const [],
    this.error,
  });

  const MeasurementSnapshot.ready()
    : this(status: SessionStatus.ready, elapsed: Duration.zero);

  final SessionStatus status;
  final Duration elapsed;
  final double? currentDb;
  final double? minimumDb;
  final double? maximumDb;
  final double? averageDb;
  final List<double> spectrum;
  final String? error;

  bool get isRunning => status == SessionStatus.running;
}

class MobileEvent {
  const MobileEvent({
    required this.id,
    required this.timestamp,
    required this.label,
    required this.confidence,
    required this.dbLevel,
    required this.status,
  });

  factory MobileEvent.fromJson(Map<String, dynamic> json) => MobileEvent(
    id: json['id'] as int,
    timestamp: DateTime.parse(json['timestamp'] as String),
    label: (json['label_de'] ?? json['label'] ?? 'Unbekannt') as String,
    confidence: (json['confidence'] as num).toDouble(),
    dbLevel: (json['db_level'] as num).toDouble(),
    status: (json['classification_status'] ?? 'automatic') as String,
  );

  final int id;
  final DateTime timestamp;
  final String label;
  final double confidence;
  final double dbLevel;
  final String status;
}
