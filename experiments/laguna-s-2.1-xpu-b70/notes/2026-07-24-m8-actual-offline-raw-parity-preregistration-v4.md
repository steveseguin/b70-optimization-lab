# Laguna M8 actual-model offline raw-parity preregistration v4

Date: 2026-07-24 America/Toronto

## Purpose and terminal predecessors

This preregisters one fresh private-NVMe, offline, nonbenchmark A/B/C
correctness gate for the actual Laguna S 2.1 target M=8 verifier. Each arm gets
exactly one `LLM.generate` call in a fresh process. The gate compares raw
evidence before any trace, timing, endpoint, benchmark, payload, or
LocalMaxxing action.

Three predecessor roots are terminal, sealed, and never reused:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-actual-offline-3fbf310f1-20260724T160003Z
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-actual-offline-820d827a3-20260724T161333Z
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-actual-offline-7f0f190d4-20260724T163134Z
```

The first aborted before EngineCore on an overlong implicit RPC path. The
second proved the short RPC layout and stopped at an incorrect eager identity
before weights or forward. The third loaded the actual target and DFlash from
internal NVMe and reached the first M=8 target-verification forward, then
stopped because the evidence hook treated the normal DFlash
`(final_hidden_states, aux_hidden_states)` result as a bare tensor. It returned
no completed generation and produced no quality or performance result.

Their immutable classifications are:

- `data/laguna-m8-actual-offline-zmq-path-preflight-abort-20260724.json`;
- `data/laguna-m8-actual-offline-eager-contract-abort-20260724.json`;
- `data/laguna-m8-actual-offline-target-hidden-evidence-abort-20260724.json`.

The approved record remains `33.89498511171744 tok/s`, LocalMaxxing
`cmrx6p5dv001bo4017hb7sixz`.

## Frozen identity

- corrected main-repo tooling:
  `6e478a38aaae548d225ffbce2a9b6d2e693e4efc`;
- approved-record vLLM ancestor:
  `8936aac144929190c1e53f8b8624ca397ce16f5b`;
- reviewed recorder, graph diagnostic, and strict DFlash unwrap vLLM:
  `00d3c7faa3a73f08246a70c7280eed633ec2441b`;
- approved-record XPU-kernel ancestor:
  `b6076ce1249ffee0e30bee528f4cd15c3bffb234`;
- frozen kernel descendant:
  `4772f727590c51b72add79350b913d098cf67872`;
- target revision:
  `4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb`;
- DFlash revision:
  `5e07c246915c86dc6920fead03d019989224f2ba`;
- exact fresh run root:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-actual-offline-6e478a38a-20260724T164716Z`.

Tool SHA-256:

```text
46967bf7c77db0f964c0aab438562695a10e18f2bd839df9524abde917b14a49  analyze_laguna_m8_actual_offline_gate.py
1f491cd89a8659c05c9d5668c2c978ade3b2e98fc61d299977f196130522cf01  capture_laguna_m8_idle_snapshot.py
8ed2ca436dd472fe5168aa8b5ea26cbda53ea958b90d14b11b724e0b0f00a3ca  run_laguna_m8_actual_offline.py
66d2a9dbb0c19075318c7862b658132983c4ee73a5a9bc95f53990600abc6fa7  run_laguna_m8_actual_offline_gate.sh
9b480c43aa4cb3930ff41ee1e69bbeab94b0a75d2668813018d0afd21df17ed1  test_analyze_laguna_m8_actual_offline_gate.py
```

The launcher also pins all four installed kernel binaries, oneCCL, SYCL,
Level Zero driver, and loader by SHA-256. Target and draft contents must pass
the retained 118-file internal-NVMe manifest. The external Corsair USB is
forbidden for active model, cache, temp, RPC, log, or evidence paths.

## Exact execution arms

All arms retain the approved BF16-KV DFlash-depth-7 stack: TP4/EP4, exact
attention/MoE, fused W1-route-W2, route-interleaved W2, W1 N64,
shared-elementwise fusion, QKNorm/RoPE fusion, standard rejection, greedy
draft, no prefix cache, no async scheduling, no warm-up, and one 32-token
`ignore_eos=true` generation.

1. `incumbent-eager` is the approved record's true eager identity:
   `enforce_eager=True`, segmentation and graph env off, and no explicit
   compilation argument.
2. `segmented-eager` uses the same true eager identity and record stack, with
   persistent buffers at the target's 97 collective boundaries.
3. `segmented-graph` uses `enforce_eager=False`, compilation mode `NONE`,
   PIECEWISE runtime capture size `[8]`, and target-only Breakable graph
   capture/replay. The drafter remains eager and logits remain outside.

The new vLLM commit changes evidence-only observation, not target execution.
It requires the already validated Laguna+DFlash target result to be an exact
two-tuple with a nonempty tensor auxiliary list and an eight-row 2-D final
hidden tensor. It records tuple element zero by identity, without rebinding or
mutating the original result that normal DFlash postprocessing consumes.
Evidence-off execution does not call the helper.

Arm A is canonical. There is no majority vote.

## Fresh RPC identity

The following exact 100-byte-with-UUID bases were confirmed absent and are
one-shot:

```text
incumbent-eager  /mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/tmp/m8p4-a
segmented-eager  /mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/tmp/m8p4-b
segmented-graph  /mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/tmp/m8p4-c
```

Each must be newly created canonical mode `0700` on `/dev/nvme0n1p2` ext4,
passed explicitly as both `VLLM_RPC_BASE_PATH` and the driver's arm argument,
recorded, analyzer-validated, and sealed after success or failure. The
platform limit is 107 bytes.

## Required evidence and stop rules

Every rank must expose at least four eligible target events. Final analysis
re-reads and hashes every manifest, sidecar, and raw tensor file and requires
exact A/B/C event identity for logical request keys, all 48 attention Q/K/V/O
tensors and live slot signatures, target hidden state and inputs,
sampled/proposed/accepted/emitted IDs, and final driver tokens. B/C must prove
all 97 collective outputs/local inputs. C must prove one descriptor, one
capture, 146 segments, 145 eager breaks, and monotonically numbered replays.
All arms must report `num_cached_tokens=0`.

Any identity, path, reuse, permission, worker, XPU-idle, model, source,
binary, environment, process, timeout, raw-byte, graph, usage, cache, or token
mismatch fails closed. This root and its RPC paths are never reused. An
operational failure requires another committed correction and preregistration.
A raw mismatch closes this graph identity.

Physical backend-owned KV packing remains explicitly unsupported by this
component recorder. A later endpoint candidate must still pass the canonical
q=1 greedy teacher, cross-start, cache-zero, long-then-next, and 863-token
rollover gates. This gate cannot produce a speed, record, or submission claim.

## Pre-execution validation and exact launch

The strict DFlash unwrap and related vLLM suites passed 66 focused tests.
The corrected main gate passed 11 tests and five subtests. Ruff, Python
formatting, shell syntax, and diff checks passed. Independent audits found no
source or launch blocker, confirmed output identity preservation, and
validated the exact vLLM/schema/RPC/A/B/C/cold-generation contracts. No model
generation was used for patch validation.

The only authorized launch is:

```bash
/usr/bin/env -i \
  PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  /usr/bin/bash \
  /home/steve/llm-optimizations/experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_m8_actual_offline_gate.sh \
  /mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-actual-offline-6e478a38a-20260724T164716Z
```
