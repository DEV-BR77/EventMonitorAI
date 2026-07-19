# Architecture Overview

EventMonitorAI separates acquisition, edge processing, persistence, review and model training.

```text
ESP32-S3 + microphone
        |
        | UDP audio frames
        v
Raspberry Pi edge service
        |
        | classified events / measurements
        v
FastAPI backend + database
        |
        +--> dashboard and integrations
        +--> EventMonitor AudioLab
```

## Design principles

1. Local-first processing and storage
2. Raw measurements remain separate from AI predictions
3. Human-confirmed labels are never overwritten by automatic predictions
4. Components communicate through documented interfaces
5. Credentials and personal recordings are never committed to Git
