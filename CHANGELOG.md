# Changelog

All notable changes to EventMonitorAI are documented in this file.

The project follows Semantic Versioning from the first tagged release onward.

## [Unreleased]

### Added

- Reproduzierbare, geheimnisfreie Installations- und Release-Pakete
- Dokumentierte Upgrade- und Rollback-Strategie für Docker Desktop
- Automatisierte PostgreSQL- und Clip-Backups mit Prüfsummen und Aufbewahrung
- Wiederherstellungsskript mit Integritätsprüfung und ausdrücklicher Freigabe
- Performance-, Last- und Ringpuffer-Langzeittests
- Security- und Datenschutzreview sowie verbindliche v1.0-Release-Kriterien

### Security

- Login-Drosselung gegen Brute-Force-Versuche
- Aktive Benutzerprüfung für authentifizierte WebSocket-Verbindungen
- Strengere Sicherheits- und Cache-Header für geschützte APIs
- Validierung produktiver Geheimnisse und exakt fixierte Abhängigkeiten

## [0.1.0] - 2026-07-19

### Added

- FastAPI backend foundation and event endpoints
- Raspberry Pi edge processing prototype
- ESP32-S3 UDP audio firmware prototype
- EventMonitor AudioLab for importing and labeling historical measurements
- GitHub Actions for CI and tagged release archives
- Contribution, security, privacy and development documentation
- Architecture overview, event model and initial AI learning concept

### Security

- Removed local credentials from tracked firmware files
- Added safe `secrets.example.h` workflow and repository ignore rules
