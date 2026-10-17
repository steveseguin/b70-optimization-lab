# Packet49b: packet49 plus exact expert GEMV kernels

CPU preparation is complete and independently verified in the separate
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

All three builds passed. Eight fresh GNU fixture runs and six ownership/lifetime
suites passed. The 12 metadata-only plan rows prove 47 IQ2 gate sites, 48 IQ4
down sites and 142 replacement banks with unchanged stored bytes. The 34
Python admission tests pass. GNU and sanitizer snapshot gates each passed
31 cases and 26 state/negative checks. Two fresh sanitizer QSA processes passed
176 checks; the dedicated expert gate passed 192 checks across two GNU and
two ASAN/UBSAN processes, with identical bytes and clean teardown.

The first expert fixture used four down-output rows and correctly hit the
unchanged production guard requiring 2,560. The corrected fixture uses the
production shape and passes. The failed attempt and its source at `122d95fba`
are preserved in the [correction receipt](../experiments/own-xpu-runtime/stage2/packet49b-gemv/p49b-fixture-correction.json).
No runtime arithmetic or production guard was relaxed.

The independent reviewer reran all 34 scoped tests, verified failure-evidence
hashes, checked sanitizer receipts/logs and verified the final seal:

`000960bb7690119fbb99723c00abc23961aab3efb6b94bfeb8734624e3e71221`

The [seal](../experiments/own-xpu-runtime/stage2/packet49b-gemv/build-receipt.json)
binds 35 artifacts and 437 sources. [Independent review](../experiments/own-xpu-runtime/stage2/packet49b-gemv/REVIEW-INDEPENDENT.md),
[CPU commands](../experiments/own-xpu-runtime/stage2/packet49b-gemv/CPU-BUILD.md).
The same packet49 oracle is still running at handoff. No device qualification
or new model speed has been claimed.

## Storage

The initial precheck saw23,371,382,784 bytes free. The conservative requirement
is22,765,608,960 bytes, leaving605,773,824 bytes above the registered budgets.
This includes8GB free floor,5.819GB for packet49's pending model outputs,
0.500GB oracle growth,2.500GB new build and5.947GB new chain peak. The queue
checks an early-retained evidence cap of128MB, including root logs; late
outputs receive no compression credit. No existing artifacts were deleted.
[Budget and limits](../experiments/own-xpu-runtime/stage2/packet49b-gemv/ARTIFACT-RETENTION.md).

The final build occupies 2.204 GB, with about 7.66 MB of separate evidence.
The [final precheck](../experiments/own-xpu-runtime/stage2/packet49b-gemv/storage-precheck.json)
records 21,219,897,344 bytes free against a remaining requirement of
20,562,094,725 bytes: **657,802,619 bytes of margin**. Completed packet49 model
windows release only their pending-write allowance after sealed receipt and
canonical queue-state validation. Existing output bytes still count in free
space. Missing or invalid receipts keep the full allowance.

Packet49's own sealed 11.486 GB reserve remains unchanged. A physical fit under
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

## Git checkpoints

- `122d95fba`: separate integration, shared oracle, queue/runbook and initial CPU preparation. Pushed immediately.
- The final seal checkpoint records the corrected fixture, all fresh gate receipts, independent review and this handoff. Its exact commit is in Git history and the coordinator report.

## Device results, 2026-10-17 (coordinator)

**Early phase on cards 0+1, chain `device-cards01-a`, 05:11-05:28 UTC: PASSED.**

- K0, K1a, K1b, K2 and W0p are all passed and qualifying.
- K1a/K1b include the `expert_gemv` device gate (p48b IQ2_S expsgate and IQ4_NL expsdown, M=1 and both M=2 rows) and the split32 QSA gate.
- No new fault lines.

**Model phase:** KD → W2m → WS → WSs → WS128x → WS128 is queued with `--wait-oracle`. It waits for the shared packet 49 CPU oracle; the oracle was 4/12 prompts complete at 05:31 UTC, projecting about 09:30.

Evidence: `device-evidence/device-cards01-a/`.
