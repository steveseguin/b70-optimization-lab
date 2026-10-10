# Stage 2 — Flash-Next packet index

Stage 2 develops our model-specific Flash-Next MoE runtime. The official
checkpoint is already local; CPU inspection of it does not authorize a model
load or a native window. [DESIGN](../DESIGN.md) remains the architecture and
placement authority. Stage 1's native packets and storage decisions remain
separate and pending.

| Packet | Status | Evidence |
| --- | --- | --- |
| 1 — Local identity, tensors, exact oracle and placement arithmetic | **CPU exit gate PASS, 2026-10-10** | [Packet and receipt](packet1/README.md) |
| Later operator, loader, layer, transaction and native qualification packets | Not authorized or executed here | [Required window and checks](packet1/README.md#next-authorized-stage-2-window) |

Packet 1 retains all 152,089 tensors, 131 shard headers and 12 complete A367
response arrays. The certified comparison is four-card TP4/EP4, native MTP1,
46.854250 tok/s; no performance or quality result for our runtime exists yet.
Two-card residency and expert-streaming byte counts are arithmetic bounds,
not a measured fit or a substitute benchmark. No existing lane was changed.
