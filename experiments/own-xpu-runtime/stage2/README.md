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
| 2 — IQ3 GGUF loader and packed dequant/GEMV kernels | **CPU exactness PASS; SYCL compiled/linked only; IQ3 on two B70s is now the first real-model target** | [Implementation, receipts and bandwidth floors](packet2/README.md), [first device window](packet2/WINDOW.md) |
| 3 — IQ3 host decode step | **23 Python tests + 18 C++ cases PASS; synthetic CPU parity only** | [Step, placement, launch plan and first device gate](packet3/README.md) |
| 4 — Integrated IQ3 CLI | **Host mini-model exact; SYCL compile/link PASS; real layer-0 oracle hash FAILS, device unrun** | [Program, CPU evidence and limits](packet4/README.md), [card-3 window](packet4/WINDOW.md) |
| 12 — Two-card TP design and peer exchange preparation | **CPU mocks/tests PASS; SYCL compile/link only; no peer measurement or model parity claim** | [Design and packet ladder](TWO-CARD-TP.md), [transport harness and cards-2/3 command](packet12-peer/README.md) |
| 13 — IQ3 performance integration and first-token capture | **CPU mini-model exact; real layer-0 frozen-order hash recorded; SYCL compile/link PASS; device unrun** | [Measured kernel dispatch, streaming/resident placement and tests](packet13-integrate/README.md), [card-3 full-model command](packet13-integrate/WINDOW.md) |
| 14 — Within-layer two-card decode | **CPU single-card/TP2/reference equality and SYCL compile checks pass; device parity and speed pending** | [Split rules, ownership and exchange census](packet14-tp2/README.md), [gated cards-2+3 commands](packet14-tp2/WINDOW.md) |
| 15 — Parallel non-GEMV candidate | **SYCL build PASS; CPU reference exactness FAIL (60/72); device unrun** | [Kernels, failure evidence, and gated card-3 commands](packet15-nongemv/README.md) |
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
