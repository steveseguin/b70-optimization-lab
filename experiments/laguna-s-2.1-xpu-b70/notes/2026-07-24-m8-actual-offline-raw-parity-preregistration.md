# Laguna M8 actual-model offline raw-parity preregistration

Date: 2026-07-24 America/Toronto

## Purpose and boundary

This preregisters one private-NVMe, offline, nonbenchmark A/B/C correctness
gate for the actual Laguna S 2.1 target M=8 verifier path. It runs exactly one
`LLM.generate` call in each of three fresh processes and compares raw evidence
before any trace, timing, endpoint, benchmark, payload, or LocalMaxxing action.

The approved record remains unchanged at `33.89498511171744 tok/s`,
LocalMaxxing `cmrx6p5dv001bo4017hb7sixz`.

This gate is not sufficient for quality promotion. Physical backend-owned KV
packing is explicitly recorded as unsupported; a later endpoint candidate must
still pass the canonical q=1 greedy teacher, cross-start, cache-zero,
long-then-next, and 863-token rollover gates.

## Frozen identity

- main-repo tooling commit:
  `3fbf310f129a59c5f28abc8b77597a5e692539d3`;
- approved-record vLLM ancestor:
  `8936aac144929190c1e53f8b8624ca397ce16f5b`;
- reviewed recorder/segmented vLLM:
  `5c6c108bf152f985e126db9d77897ae442b75048`;
- approved-record XPU-kernel ancestor:
  `b6076ce1249ffee0e30bee528f4cd15c3bffb234`;
- frozen kernel descendant:
  `4772f727590c51b72add79350b913d098cf67872`;
- target revision:
  `4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb`;
- DFlash INT4 revision:
  `5e07c246915c86dc6920fead03d019989224f2ba`;
- exact run root:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-actual-offline-3fbf310f1-20260724T160003Z`.

Tool SHA-256:

```text
f4b247a5ac09df8c3b3024a7f5a8a86f41c48c5e0c08182a898a90f70e2639c6  analyze_laguna_m8_actual_offline_gate.py
1f491cd89a8659c05c9d5668c2c978ade3b2e98fc61d299977f196130522cf01  capture_laguna_m8_idle_snapshot.py
4a68c0a1e9b8a443180e27ded1a61038499c4cfca0ee98a7e2653fc68974ed29  run_laguna_m8_actual_offline.py
7dce24c319cfd8e73038cb6b330ffae82bc53994f8f91afe3a767032f0def682  run_laguna_m8_actual_offline_gate.sh
85812a217f290faff54020f65ac2cd0f018e8b6c866b75618eb1a511120be816  test_analyze_laguna_m8_actual_offline_gate.py
```

The launcher separately pins the four installed kernel binaries, oneCCL,
SYCL, Level Zero driver, and Level Zero loader by SHA-256. Target and draft
model contents must pass the retained 118-file NVMe manifest before any arm.
The external Corsair USB is forbidden for model reads, cache, temp, logs, or
evidence.

## Arms

All arms use the same reviewed vLLM source, target and DFlash revisions,
approved record kernel binaries, TP4/EP4 topology, BF16 KV, exact M8
attention/MoE, route-interleaved W2, W1 N64, shared-elementwise and
QKNorm/RoPE record stack, greedy draft, standard rejection, depth 7, no
prefix cache, no async scheduling, no warm-up, and one 32-token
`ignore_eos=true` generation.

1. `incumbent-eager`: actual incumbent eager execution, segmented selectors
   off, no graph.
2. `segmented-eager`: the same target source with all 97 in-model collectives
   in persistent eager buffers, no graph.
3. `segmented-graph`: the same segmented source with target-only M=8
   Breakable graph capture/replay; the drafter remains eager and logits remain
   outside the target wrapper.

Arm A is canonical. There is no majority vote.

## Required raw evidence

Every rank must expose at least four eligible target events: one capture plus
at least three replays for the graph arm. The analyzer requires exactly four
rank streams with equal event counts and compares, event by event:

- logical candidate IDs, positions, request-generation epoch, target ordinal,
  sequence/query metadata, and live slot mapping;
- all 48 target attention query, key, value, and output tensors plus each live
  per-layer slot signature;
- target hidden state before logits plus input IDs, positions, and slot
  signature;
- sampled token IDs, seven proposed draft IDs, accepted-prefix metadata, and
  emitted IDs before and after bookkeeping;
- B/C raw output and local-input signatures for the embedding all-reduce plus
  all 96 in-model all-gathers; and
- one graph descriptor, exactly one capture, 146 graph segments, 145 eager
  breaks, and monotonically numbered later replays.

Every recorder manifest must carry
`LAGUNA_M8_RAW_EVIDENCE_V1`. Every raw file and event sidecar is re-read,
re-hashed, and compared with its manifest during final analysis. The stored
aggregate must equal a fresh aggregate regenerated from raw evidence.
A/B/C final emitted token-ID lists must be identical and every arm must report
`num_cached_tokens=0`.

## Stop and continuation rules

- Any identity, path, permission, worker, XPU-idle, model-content, process,
  timeout, manifest, sidecar, raw-byte, event-order, signature, graph,
  acceptance, usage, cached-token, or final-token mismatch fails closed.
- A failed root is immutable and is never reused. A raw-parity failure closes
  this segmented graph identity. An operational/tooling failure requires a
  separately committed correction and new preregistration; it is not silently
  retried.
- No timing or PTI claim is made by this gate.
- A pass authorizes only construction and preregistration of separate fresh
  PTI-trace and component-timing work. It does not authorize an endpoint,
  benchmark payload, record claim, or submission.
- Only after separate trace/timing clears its frozen gate may a fresh cold
  endpoint crossover run. Any endpoint candidate must then pass the complete
  canonical teacher and request-boundary exactness suite before it can be
  considered against the approved LocalMaxxing record.

## Pre-execution validation

Before this registration, the focused main-repo suites passed 26 tests plus
31 subtests, the reviewed vLLM recorder suites passed 14 tests, Ruff and shell
syntax passed, and an independent read-only audit reported no launch blocker.
No model or XPU generation was used to obtain those validation results.
