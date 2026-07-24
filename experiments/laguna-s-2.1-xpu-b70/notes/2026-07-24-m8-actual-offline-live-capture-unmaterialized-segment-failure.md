# Laguna M8 live-capture unmaterialized-segment correctness failure

Date: 2026-07-24 America/Toronto

## Result first

The preregistered v9 actual-model gate completed all three arms and failed
closed during the final B/C raw comparison. Arms A and B are exactly
identical. Arm C captured the intended graph once and replayed it thereafter,
but its first live capture consumed an unmaterialized first graph segment and
immediately departed from canonical output. This is a real graph-correctness
failure, not analyzer noise, performance evidence, a benchmark, a payload, or
a LocalMaxxing result.

The immutable sealed root is:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-actual-offline-4f93bd939-20260724T192555Z
```

It must never be reused. The approved record remains
`33.89498511171744 tok/s`, LocalMaxxing
`cmrx6p5dv001bo4017hb7sixz`.

## What completed

All arms used one fresh offline generation, reported exactly zero cached
tokens, finished by length at 32 completion tokens, wrote v9 drivers and
v10/raw-V2 aggregates, and passed post-worker and post-idle cleanup.

Arms A (`incumbent-eager`) and B (`segmented-eager`) are bitwise identical:

```text
token IDs  cca03973c1998dfc3255cad724577213ed01cb606cf12eb867358de16f9b9e3f
text       92105d1de6f357cac164f12b76adc090c334135477400010f3e1e810109efd0b
```

Arm A retained 60 manifests, 15 per rank, with 201 events each. Arm B
retained 60 manifests, 15 per rank, with 444 events each. Arm C retained 64
manifests, 16 per rank, with 446 events each. Its first event on every rank is
`capture`; every later event is `replay`, with capture count fixed at one,
descriptor fixed at exact M=8, 146 graph segments, and 145 eager breaks.

Arm C is not correct:

```text
token IDs  05ac826fdf4e9251e63d13142e2bbfa1e35c49e0e0a4aa40c33b4ae07e75bdd1
text       3cdcad001051105acaf3e4d6ec11e37e2bf136ed215fdba663d960e1e0505a27
```

The first generated token (`268`) matches because it precedes the eligible
M=8 target transaction. At the first eligible transaction, canonical B emits
token `19`; C emits token `0`. The changed acceptance path requires one extra
eligible transaction, so C has 16 events per rank versus B's 15. The analyzer
therefore stops at the earlier structural invariant:

```text
B/C: rank 0 missing/extra eligible event
```

No final `analysis.json` exists, as required for a failed gate.

## Earliest raw divergence and root cause

Rank 0 event 0 has an identical logical key in B and C: candidate IDs,
positions, request epoch, target ordinal, M=8 shape, and all 48 attention slot
mapping signatures match. Physical KV status also matches.

The earliest data divergence is before the first eager collective executes:

```text
B embedding_all_reduce local/output
  sha256   1f3f00c08efcc9b35a9987ca87dd6aa4163a03fcc0e3d259638bfee82910fe6b
  bytes    49152 BF16 [8,3072]
  nonzero  49069 bytes

C embedding_all_reduce local/output
  sha256   2aae7dc846aaf25f1cadf55f1666862046c6db9d65d84bdc07fa039dac405606
  bytes    49152 BF16 [8,3072]
  nonzero  0 bytes
```

The C digest is exactly SHA-256 of 49,152 zero bytes. The collective uses a
distinct fixed output, copies the already-zero local input, then all-reduces
it. It cannot be the origin. The logical key and slot routing rule out a
scheduler or KV-slot mismatch.

`BreakableCUDAGraphCapture` records graph kernels during capture without
executing them; its CUDA tests explicitly assert this behavior. The wrapper's
normal contract assumes capture happens during a disposable warmup and that a
later invocation performs the first replay. Laguna's guarded lane instead
does the first capture lazily on the live exact M=8 transaction and returns
that capture-time output to the request. Therefore the first captured
embedding segment has not run when its eager all-reduce boundary consumes the
buffer. The zero embedding corrupts the rest of the live forward, and later
replays faithfully reproduce a graph built around that invalid capture-time
handoff.

The next correction must be narrow and testable: only the guarded live
Laguna lane may materialize each newly ended graph segment before its
capture-time eager consumer, including the final segment before returning.
The generic breakable-graph warmup semantics must remain unchanged. Tests must
prove ordered graph/eager materialization, one capture followed by replay,
exception cleanup, and no behavior change for the default wrapper.

## Cleanup and artifact state

The root is sealed mode `0500`. All arm post-idle snapshots passed, all
post-worker reports are empty, and no runner or analyzer process remains.
Models and artifacts stayed on internal NVMe under `/mnt/fast-ai`; the backup
USB was not used.

## Frozen identities and hashes

- main tooling:
  `4f93bd939cfc52311162200e63119da391184195`;
- preregistration:
  `7de834dbd2e03fee6a625de2337eee9448385186`;
- vLLM:
  `7e674bfbd05100383dc9e949f813fa7483b53cc3`;
- XPU kernels:
  `4772f727590c51b72add79350b913d098cf67872`;
- RPC paths: `m8p9-a`, `m8p9-b`, and `m8p9-c`;
- driver schema: `laguna-m8-offline-arm-v9`;
- aggregate schema: `laguna-m8-actual-offline-gate-v10`;
- raw format: `laguna-m8-raw-evidence-v2`.

Key retained hashes:

```text
d4daffc10969cd77893c1015414986f00ba54eac5eed95e446c583b6c3834aff  identity.txt
923cdd4dec3435a8d2c5ef90a0dcdc5534e43a84a7106d4dab091510ce1974d3  incumbent-eager/driver.json
bff0a536e3a74c7d1d5b3489c568de62252449f4d7d278a5a90b43dad62cfb12  incumbent-eager/evidence/evidence.json
e6fcf8d9a866713eb3bc6e8130375c29b6ad16ebd977497535270e3c142f430f  segmented-eager/driver.json
a0fd25d39062b917abd126e031a0f8425642ff2959145189034c73de21635d08  segmented-eager/evidence/evidence.json
2d7c8b07f9d4afece2b549c3765da9ae4d01cecf63fda8239708195f6bf75d8b  segmented-graph/driver.json
ffe287d26faa37f0de4e36e070d67a7fec4ad70ab07fc03f09a6c36833bd2454  segmented-graph/evidence/evidence.json
```

Machine-readable classification:
`data/laguna-m8-actual-offline-live-capture-unmaterialized-segment-failure-20260724.json`.
