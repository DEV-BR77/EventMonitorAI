# Event Model

An **event** is a time-bounded acoustic observation. A **case** groups related events into one larger incident.

## Event fields

- start and end timestamp
- source device
- average and maximum sound level
- predicted class and confidence
- confirmed class and reviewer status
- optional audio reference, notes and feature metadata

## Initial classes

Priority classes are screaming, calling, argument or multiple loud voices, impact or striking, door slam, car, motorcycle and horn. Normal speech and environmental sounds are retained as negative classes to reduce false positives.

The system identifies acoustic patterns. It does not establish who caused an event or prove intent.
