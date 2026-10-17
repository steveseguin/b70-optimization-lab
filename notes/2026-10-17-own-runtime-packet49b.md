# Packet49b: packet49 plus exact expert GEMV kernels

CPU preparation is in progress in the separate
`experiments/own-xpu-runtime/stage2/packet49b-gemv/` packet. No GPU work is
performed by this task. The coordinator owns the device windows; packet49's
sealed tree and running `own-iq3-p49-oracle-20261017b.service` are untouched.

## Scope and integration

The candidate adds the production-screened IQ2_S expert gate/up and IQ4_NL
down paths to packet49, for M=1 and each M=2 row wherever the existing engine
calls them. GDN QKV/Z M=2 is excluded because packet48b only measured M=1 in
production-matched form; the M=1 dense screen was not worthwhile. Exceptional
IQ3_S gate remains unchanged.

The default p48b final row padding would exceed the unchanged30GiB arena cap.
A four-byte final row stride preserves all actual load alignments and keeps
packed banks the same size as before. Within-row plane offsets, arithmetic,
route/status checks and scheduling remain unchanged. This addressing change
requires fresh device qualification; no p48b timing is claimed for packet49b.
[Integration details](../experiments/own-xpu-runtime/stage2/packet49b-gemv/INTEGRATION.md).

The arithmetic is still `iq3-p49-split32-v1`. Packet49b reuses the exact
packet49 CPU oracle through a read-only symlink and static hash binding.
Each model-window receipt also binds its completed manifest, determinism,
KD capture and completion receipt. The existing oracle unit is never altered.

## CPU preparation and review

Builds use nice19, cores4–15,20–31 and one compiler at a time, with
`python3 -B`. GNU host, Intel device compilation and GNU ASAN/UBSAN are the
registered build modes. No device binary is executed. No model payload,
service, sudo, power, memory, swap or page-cache operation is part of this task.
The independent reviewer confirmed compact-pitch load alignment and shared
oracle binding. Review found an inherited stale suite-identity literal; the
new packet corrects it while preserving metric formulas.

Final gate receipts and seal will be recorded after the serial builds finish.

## Storage

The initial precheck saw23,371,382,784 bytes free. The conservative requirement
is22,765,608,960 bytes, leaving605,773,824 bytes above the registered budgets.
This includes8GB free floor,5.819GB for packet49's pending model outputs,
0.500GB oracle growth,2.500GB new build and5.947GB new chain peak. The queue
checks an early-retained evidence cap of128MB, including root logs; late
outputs receive no compression credit. No existing artifacts were deleted.
[Budget and limits](../experiments/own-xpu-runtime/stage2/packet49b-gemv/ARTIFACT-RETENTION.md).

Packet49's own sealed11.486GB reserve remains unchanged. A physical fit under
the new packet's scope does not guarantee packet49's stricter later admission
will pass after other disk writes. All checks use current space and stop on
refusal; neither chain silently spends an unlimited reserve.

## Coordinator handoff and record scope

[Exact commands](../experiments/own-xpu-runtime/stage2/packet49b-gemv/WINDOW.md)
use a fresh `packet49b-gemv/build/device-cards01-a` chain:
K0 → K1a → K1b → K2 → W0p, then after the same oracle completes,
KD → W2m → WS → WSs → WS128x → WS128.

WS128 is the final speed measurement:12 prompts,128 tokens,capacity4096.
It requires the WS128x exactness companion. The class-balanced primary uses
99/(t100-t1); the all-prompt median is stored separately. Prompt/output hashes,
timestamps, event/interval counts and all original metric definitions remain.
The39.422 record is unchanged. This128-token comparison does not pass the
separate512-token publication gate or establish a new submitted record.
