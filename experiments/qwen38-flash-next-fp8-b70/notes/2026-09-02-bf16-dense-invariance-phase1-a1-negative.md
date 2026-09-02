# Qwen3.8 Flash-Next BF16 dense-invariance Phase 1 A1 negative

Date: 2026-09-02

Status: failed closed before the first cell could be accepted

## Result

The independently reviewed 168-process census stopped inside its first worker,
before writing a cell result. The two 256-row singleton sweeps used as the M1
authority produced different aggregate BF16 hashes, so the worker raised
`singleton authority is not repeat-qualified`. It loaded only the first real
weight sentinel on one B70; no server, endpoint, container, or full model was
started.

This is useful negative evidence, but it is not yet proof of steady-state BF16
GEMM nondeterminism. The first sweep also contained the provider's first 256
calls, and A1 discarded row-level details on mismatch. The reconstructed
`hc_down_inject` weight has 324 consumed output columns followed by 12
synthetic zero-padding columns, so padding-only drift would not imply model
output drift.

## Launch detail

The first detached user-service invocation stopped before evidence creation
because its read-only SMART check could not open the root controller. The
device attempt then ran as the same `steve` user in a transient system service
with only the capabilities required for that SMART query. It passed admission,
created and validated the historical-receipt-backed shard contract, and then
stopped on the singleton gate. The system journal records exit status 1; the
service wrapper did not hide or reinterpret it.

## Decision

Do not continue the remaining 167 processes. A2 must reproduce the exact cold
pair before any warmup, retain immutable CPU snapshots, report active columns
0:324 separately from padding columns 324:336, compare queued and per-call-
synchronized modes, preserve loaded-library identity, and always write a
postflight-valid diagnostic envelope even when a check fails. No protected
quality or speed result changes.

Structured result:
[`../data/20260902-bf16-dense-invariance-phase1-a1-negative.json`](../data/20260902-bf16-dense-invariance-phase1-a1-negative.json)
