# Qwen3.8 Flash-Next BF16 singleton A2 preregistration

Date: 2026-09-02

Status: frozen before device execution; A1 preserved

## Trigger and question

Phase-1 A1 stopped on its first planned cell before writing cell evidence. The
two independently constructed 256-row singleton-authority hashes differed for
`hc_down_inject`, sentinel `layer00-attn-r0`, seed `2026090201`, replica 1.
The A1 service log SHA-256 is
`15b651edd9c3bdc2f2070d286f6faae33414ad143ca02d61d984e9d5a099e10c`.
Its frozen shard contract remains intact: physical SHA-256
`6b82f878734c32099f7dbb0491a0ede061d00fbe7d9c4b4e4e0a49433090a5be`
and canonical SHA-256
`8ff2556748595bb736ea25caded6bf62cb7c37d8dd0eba0e2819d10f24e179d8`.

A1 did not preserve its two mismatching output hashes, so it cannot distinguish
an M1 `F.linear` repeatability failure from cold initialization, queued-output
lifetime, or the synthetic output tail. A2 answers only that question. It
does not resume the 168-cell census.

## Exact scope and ordering

A2 imports the exact A1 tool at SHA-256 `e4700fc4...` and reuses its external
checkpoint, current-boot clearance, source/runtime identities, shard receipt,
active-owner refusal, lock, native-provider contract, and health gates. It
uses exactly the failed weight, input construction, seed, and one selected B70.
Two fresh subprocess replicas are required.

After CPU weight/input construction and unavoidable device transfer, the first
GEMM workload is an exact cold A1-style pair: 256 queued M1 calls, list-to-cat,
synchronize and host snapshot, repeated twice. Nothing warmed or immediately
snapshotted precedes that pair. It is followed by:

- four 256-row passes that synchronize and copy each M1 row immediately;
- four warmed A1-style queued-list/cat passes;
- 20 immediate repeats for rows `0,1,2,31,63,127,191,255`.

Every invocation records a full hash and per-row hashes. Shape, BF16 dtype,
finite values, input/weight immutability, Torch version/build identity,
safetensors identity, and validated native mappings before and after GEMMs are
required. A worker is capped at 600 seconds and the two-worker plan at 1,500
seconds.

## Active output versus synthetic padding

This N=336 weight is 320 down columns plus four active inject columns and 12
synthetic zero-padding columns. A2 therefore records independent aggregate and
per-row hashes for active output columns `0:324` and synthetic padding columns
`324:336`. Every comparison reports differing row/column sets, element counts,
BF16 bit pairs, and per-row magnitude statistics for both regions. Every
invocation also audits whether the synthetic tail is numerically zero and
records any nonzero tail coordinates/bits.

Frozen interpretation priority:

1. warmed immediate/fixed-row active differences: genuine warmed M1 active
   output repeatability failure;
2. warmed deferred-only active differences: queued-output/lifetime failure;
3. cold-pair-only active differences: cold-start active instability not
   reproduced warm;
4. differences confined to `324:336`: synthetic-tail instability, explicitly
   **not** production-output nondeterminism;
5. no differences in either fresh process: bounded A1 mismatch not reproduced.

Any cross-process active-region mismatch participates in the same distinction.
If the replicas' input or reconstructed-weight hashes differ, however, A2 emits
`diagnostic_error` / `identity_drift_no_interpretation` and bypasses arithmetic
inference entirely.
No result authorizes a runtime patch, performance claim, quality claim, or A1
reinterpretation without a separately preregistered follow-up.

## Failure preservation

Each child writes one no-clobber diagnostic envelope even for mutation,
provider, or child-postflight failure. The parent runs and preserves its own
postflight in a `finally` path even if the child errors or times out, and creates
a missing-child envelope if a hard timeout prevents the worker from doing so.

Structured preregistration:
[`20260902-bf16-singleton-a2-prereg.json`](../data/20260902-bf16-singleton-a2-prereg.json).
