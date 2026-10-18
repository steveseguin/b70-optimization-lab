# Packet58c GPUActive accounting — CPU closeout

<!-- campaign-closeout -->

## Question and identity

Can packet58b's unchanged one-card IQ3 engine load while keeping the admitted
118.309 GB host budget, when pinned experts appear in GPUActive? October 17,
2026; wrapper-only source copy, native arithmetic `iq3-p49-split32-v1` unchanged.

## Outcome

The new wrapper separates completed census-checked pins from residual shadow
and enforces a combined host budget. Retained snapshot replay and synthetic
positive/negative cases pass. Native binaries are inherited byte for byte.
No device result or full-model fit is claimed.

## What worked

78 completed expert banks total 26.424 GB, just above the old 26.409 GB shadow
cap. Explicit accounting avoids treating those banks as extra shadow. Unknown,
duplicate or wrong-size progress rows fail closed. Samples are now retained on
every poll, including the one that triggers a memory stop.

## What failed or remains uncertain

58b retained only before/end host snapshots and a last supervisor sample during
drain. It discarded the actual offending sample; progress rows have no times.
The pinned-USM explanation fits the evidence but cannot be fully established
from that sparse record. 120.9 GB available is an endpoint observation, not a
measured minimum during loading. The last retained drain sample had 115.026 GB
available. Device confirmation belongs to the coordinator. No NEO override was
present. An unrelated inherited ledger pin was stale and was refreshed in 58c
only after checking that no matching one-card submission had appeared.

## Evidence and patches

- [Frozen KD evidence copy and original hashes](evidence/58b-kd/source-manifest.json).
- [Replay and mechanism accounting](evidence/sensor-replay.json).
- [Sensor implementation](window.py), [CPU tests](test_memory_sensor.py).
- [CPU gate log](evidence/python-cpu-gates.log), [build provenance](CPU-BUILD.md).
- [Parent source/latch pins](parent58b-source-manifest.json).

## When to revisit

The coordinator reviews the retained 58b latch, then runs the planned fresh
K1a → K1b → KD → W2m → WS → WS128x → WS128 chain on card 0. Existing rules
forbid cross-seal K1 reuse. Review the new time-stamped accounting before any
further memory changes. Frozen packet trees, screen and ops remain untouched.
