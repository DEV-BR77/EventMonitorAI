# Performance- und Langzeittests

## Automatisierte Grenzen

Die Testsuite enthält zwei reproduzierbare Regressionstests:

- 20.000 Ereignisse werden in einer Dashboard-Statistik unter fünf Sekunden
  ausgewertet.
- Eine Stunde Audioübertragung in 100-ms-Paketen wird ohne unbeschränktes
  Speicherwachstum simuliert; der Ringpuffer bleibt exakt fünf Sekunden groß.

Der HTTP-Lasttester kann gegen Health- oder geschützte Endpunkte laufen:

```powershell
.\.venv\Scripts\python.exe scripts\load_test.py `
  --url https://dashboard.eventmonitor.eu/health `
  --duration 30 --concurrency 16 `
  --max-error-rate 0.001 --max-p95-ms 500
```

Für geschützte Endpunkte wird ein kurzlebiger Testtoken über `--token`
übergeben. Tokens gehören nicht in Skripte, Shell-Historien oder Ergebnisdateien.

## Verifizierter Produktionslauf vom 9. August 2026

| Kennzahl | Ergebnis |
|---|---:|
| Dauer / Parallelität | 30 s / 16 Clients |
| Anfragen | 6.776 |
| Fehler | 0 |
| Durchsatz | 225,87 Anfragen/s |
| Mittelwert | 70,76 ms |
| p50 / p95 / p99 | 64,29 / 100,10 / 285,29 ms |

Der Lauf erfüllte die Abnahmekriterien von höchstens 0,1 % Fehlern und p95
unter 500 ms. Ein Health-Test ersetzt keinen Endpunkt- und Datenbanklasttest;
vor einem v1.0-Tag muss deshalb zusätzlich ein mindestens 24-stündiger Soak-
Test auf der Zielhardware dokumentiert werden.
