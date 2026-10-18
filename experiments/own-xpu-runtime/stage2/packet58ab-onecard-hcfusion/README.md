# Packet58ab: one-card target HC fusion

Port packet60's exact norm, low/activation plus inject, and gate/mix stages to
packet58z's one-card source closure. This is CPU preparation, not a speed claim.
The target, oracle, tile16, all 48 layers, 21,552,729,600-byte cache, overlap,
BF16 KV and context 4096 remain unchanged. Final HC and draft are excluded.

`hc=production|p60fusion` is a runtime dimension at a quiescent boundary.
The smoke is twelve 64-token requests. The five-view comparison uses one load
and twelve 128-token requests per view: production/fusion/production/fusion/
production. A0 must be exact and is reported, but excluded from drift and gain.
The two warm controls must stay within 3%; both fusion views must beat both
controls by at least 2% for this port's speed gate. Fresh-start and final
promotion gates remain separate.

Nothing is queued. READY-FOR-DEVICE.json is valid only when written last,
with current commit, proposal hashes and all CPU/entry/planning checks.

[Work note](../../../../notes/2026-10-18-own-runtime-packet58ab.md).
