# Packet127: exact target-head split retune

Separate copy of frozen packet124 bundle7 sources with fixed drain waiting.
The only runtime dimension is the rank0 suffix: 46,080, 81,920 or 122,880
rows. Each view selects a registered partition before allocation; prepared
kernels retain the same per-row arithmetic and merge rule. Draft prefix,
24/24 layers and BF16 KV remain fixed.

[Preregistration and progress](../../../../notes/2026-10-18-own-runtime-packet127.md).
CPU preparation and coordinator-only device proposals are in progress.
No GPU job, live queue or service is started by this packet's CPU workflow.
