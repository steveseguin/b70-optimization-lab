# Stage 2 — Flash-Next packet index

Stage 2 develops our model-specific Flash-Next MoE runtime. The official
checkpoint is already local; CPU inspection of it does not authorize a model
load or a native window. [DESIGN](../DESIGN.md) remains the architecture and
placement authority. Stage 1's native packets and storage decisions remain
separate and pending.

| Packet | Status | Evidence |
| --- | --- | --- |
| 1 — Local identity, tensors, exact oracle and placement arithmetic | **CPU exit gate PASS, 2026-10-10** | [Packet and receipt](packet1/README.md) |
| 1b — CPU reference math and Stage 2 plan | **37 synthetic checks PASS; device parity UNVERIFIED, 2026-10-10** | [Packet/receipts](packet1b/README.md), [plan and owner decisions](../STAGE2-PLAN.md) |
| 1c — Actual Unsloth mixed-grid header census | **CPU census PASS; IQ3 first, IQ4 weight-only rejection corrected; MTP absent** | [Census, comparison and fetch receipt](packet1c/README.md) |
| Later operator, loader, layer, transaction and native qualification packets | Not authorized or executed here | [Required window and checks](packet1/README.md#next-authorized-stage-2-window) |

Packet 1 retains all 152,089 tensors, 131 shard headers and 12 complete A367
response arrays. The certified comparison is four-card TP4/EP4, native MTP1,
46.854250 tok/s; no performance or quality result for our runtime exists yet.
Two-card residency and expert-streaming byte counts are arithmetic bounds,
not a measured fit or a substitute benchmark. No existing lane was changed.

The separate [Qwen3.8 Flash-Next UD-IQ3_XXS (Unsloth), quantized compressed
version lane](../../qwen38-flash-next-ud-iq3xxs-b70/README.md) now has a
[passing real-weight admission packet](../../qwen38-flash-next-ud-iq3xxs-b70/packet1/README.md):
all three shard hashes, all 1,224 descriptors and bounded fresh-process CPU
fixtures pass; no inference result or native fit claim exists. Its own oracle
and records follow the owner's separate-model decision, with no FP8 tolerance gate.
