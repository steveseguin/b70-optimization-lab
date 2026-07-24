# Laguna M8 actual-model offline raw-parity preregistration v5

Date: 2026-07-24 America/Toronto

## Purpose and terminal predecessors

This preregisters one fresh private-NVMe, offline, nonbenchmark A/B/C
correctness gate for the actual Laguna S 2.1 target M=8 verifier. Each arm gets
exactly one `LLM.generate` call in a fresh process. The gate compares raw
evidence before any trace, timing, endpoint, benchmark, payload, or
LocalMaxxing action.

All earlier roots are terminal, sealed, and never reused. The most recent v4
root is:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-actual-offline-6e478a38a-20260724T164716Z
```

Its A arm loaded target and DFlash from internal NVMe, completed all 15 target
verifier events on all four ranks, and returned exactly one cache-zero
generation. Post-generation aggregation then failed before `driver.json`
because the v1 evidence schema incorrectly required all 48 attention layers
to share the first layer's slot mapping. Laguna's hybrid cache legitimately
uses multiple per-layer mappings. B and C did not run; the returned 32-token
completion was not persisted; this is not a benchmark, quality, or performance
result. Preserve:

- `experiments/laguna-s-2.1-xpu-b70/notes/2026-07-24-m8-actual-offline-hybrid-slot-schema-abort.md`;
- `data/laguna-m8-actual-offline-hybrid-slot-schema-abort-20260724.json`.

The approved record remains `33.89498511171744 tok/s`, LocalMaxxing
`cmrx6p5dv001bo4017hb7sixz`.

## Frozen identity

- corrected main-repo tooling:
  `598dc430deb8d090a75c9b294a6c584125521013`;
- approved-record vLLM ancestor:
  `8936aac144929190c1e53f8b8624ca397ce16f5b`;
- reviewed recorder, graph diagnostic, DFlash unwrap, and hybrid-slot vLLM:
  `00ba70bdbf4b5f9bd5714c288b98c54c91637c53`;
- approved-record XPU-kernel ancestor:
  `b6076ce1249ffee0e30bee528f4cd15c3bffb234`;
- frozen kernel descendant:
  `4772f727590c51b72add79350b913d098cf67872`;
- target revision:
  `4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb`;
- DFlash revision:
  `5e07c246915c86dc6920fead03d019989224f2ba`;
- exact fresh run root:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-actual-offline-598dc430d-20260724T172414Z`.

Tool SHA-256:

```text
4da131b3a233e3909bea20e1b62bf57da605504cd1ec58673d9bd7b8c0a08ccc  analyze_laguna_m8_actual_offline_gate.py
1f491cd89a8659c05c9d5668c2c978ade3b2e98fc61d299977f196130522cf01  capture_laguna_m8_idle_snapshot.py
99ea295ad3432c5b66aab91a4319f1d6bec827883548be7d10d5d1f77bf01e55  laguna_nvme_paths.sh
212c7bab469289ec2071b034155054563ad4be585b884d351c70f44ce3f8a810  run_laguna_m8_actual_offline.py
2931a42673744bc1f95b3808bfa06fe4049c02d13c0a4be1cf664968407fb73f  run_laguna_m8_actual_offline_gate.sh
40d092daf3d5ddb6123abfbfb948accf7afd856ae3561fe4033d65f0276c77ad  test_analyze_laguna_m8_actual_offline_gate.py
```

The launcher also pins installed kernel binaries, oneCCL, SYCL, the Level Zero
driver, and the loader by SHA-256. Target and draft contents must pass the
retained 118-file internal-NVMe manifest. The external Corsair USB is forbidden
for active model, cache, temp, RPC, log, or evidence paths.

## V2 evidence contract

The evidence-only schema now records a canonical ordered vector of exactly 48
attention slot-mapping signatures, one for every
`model.layers.N.self_attn.attn`. The runtime requires every mapping to be a
contiguous int64 `[8]` tensor, preserves numerical layer order, and validates
device, shape, stride, byte count, and SHA-256.

For every layer, the analyzer independently requires all four live Q/K/V/O
slot signatures to agree and requires that live signature to equal the
logical vector entry for that layer. A/B and B/C compare the complete live
routing vector separately from raw tensor evidence. Distinct mappings between
layers are valid; within-layer, logical/live, rank/device, geometry, or
cross-arm drift fails closed. Target-hidden evidence contains only its actual
`input_ids` and `positions` inputs.

This changes evidence observation only. Evidence-off execution remains
untouched and target arithmetic, outputs, cache contents, DFlash state, and
kernel selection are not mutated.

## Exact execution arms and fresh RPC identity

All arms retain the approved BF16-KV DFlash-depth-7 stack: TP4/EP4, exact
attention/MoE, fused W1-route-W2, route-interleaved W2, W1 N64,
shared-elementwise fusion, QKNorm/RoPE fusion, standard rejection, greedy
draft, no prefix cache, no async scheduling, no warm-up, and one 32-token
`ignore_eos=true` generation.

1. `incumbent-eager`: true eager, segmentation and graph off.
2. `segmented-eager`: true eager with persistent collective-boundary buffers.
3. `segmented-graph`: compilation mode `NONE`, PIECEWISE capture size `[8]`,
   target-only Breakable capture/replay; draft and logits remain eager.

Arm A is canonical. There is no majority vote.

The following exact 100-byte-with-UUID RPC layouts and run root were confirmed
absent before this preregistration and are one-shot:

```text
incumbent-eager  /mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/tmp/m8p5-a
segmented-eager  /mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/tmp/m8p5-b
segmented-graph  /mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/tmp/m8p5-c
```

Each path must be newly created canonical mode `0700` on
`/dev/nvme0n1p2` ext4, recorded, analyzer-validated, and sealed after success
or failure.

## Required evidence and stop rules

Every rank must expose at least four eligible target events. Final analysis
re-reads and hashes every manifest, sidecar, and raw tensor file and requires
exact A/B/C event identity for logical request keys, all 48 attention Q/K/V/O
tensors and live slot routing, target hidden state and inputs,
sampled/proposed/accepted/emitted IDs, and final driver tokens. B/C must prove
all 97 collective outputs/local inputs. C must prove one descriptor, one
capture, 146 segments, 145 eager breaks, and monotonically numbered replays.
Every arm must report `num_cached_tokens=0`.

Any identity, path, reuse, permission, worker, XPU-idle, model, source,
binary, environment, process, timeout, raw-byte, graph, usage, cache, or token
mismatch fails closed. This root and its RPC paths are never reused. An
operational failure requires another committed correction and preregistration.
A raw mismatch closes this graph identity.

Physical backend-owned KV packing remains outside this component recorder. A
later endpoint candidate must still pass the canonical q1 greedy teacher,
cross-start, cache-zero, long-then-next, and 863-token rollover gates. This
gate cannot produce a speed, record, payload, or submission claim.

## Pre-execution validation and exact launch

The full related vLLM CPU-only suite passed 66 tests. The main analyzer suite
passed 16 tests plus five subtests. Ruff lint/format, shell syntax, diff, and
source-identity checks passed. Independent read-only audits found no blocker
and validated the V2 schema, logical/live routing bind, immutable pins,
NVMe-only policy, exact 100-byte RPC calculation, A/B/C identities, and
fail-closed behavior. No model or XPU work was used for patch validation.

The only authorized launch is:

```bash
/usr/bin/env -i \
  PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  /usr/bin/bash \
  /home/steve/llm-optimizations/experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_m8_actual_offline_gate.sh \
  /mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-actual-offline-598dc430d-20260724T172414Z
```
