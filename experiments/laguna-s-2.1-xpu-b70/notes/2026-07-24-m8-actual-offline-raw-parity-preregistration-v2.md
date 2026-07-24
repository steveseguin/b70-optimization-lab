# Laguna M8 actual-model offline raw-parity preregistration v2

Date: 2026-07-24 America/Toronto

## Purpose and prior abort

This preregisters one fresh private-NVMe, offline, nonbenchmark A/B/C
correctness gate for the actual Laguna S 2.1 target M=8 verifier path. Each arm
gets exactly one `LLM.generate` call in a fresh process. Raw evidence is
compared before any trace, timing, endpoint, benchmark, payload, or
LocalMaxxing action.

The first preregistered root is terminal and remains sealed:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-actual-offline-3fbf310f1-20260724T160003Z
```

It aborted before EngineCore, workers, model load, XPU generation, or evidence
because the implicit RPC base inherited a long private `TMPDIR`. The retained
classification is
`data/laguna-m8-actual-offline-zmq-path-preflight-abort-20260724.json`.
This v2 run changes only the RPC socket location. It makes no inference from,
and does not reuse, the first root.

The approved record remains unchanged at `33.89498511171744 tok/s`,
LocalMaxxing `cmrx6p5dv001bo4017hb7sixz`.

## Frozen identity

- corrected main-repo tooling commit:
  `820d827a383e580eb0d6a9573d8b9a78bd5861d2`;
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
- exact fresh run root:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-actual-offline-820d827a3-20260724T161333Z`.

Tool SHA-256:

```text
ced84165587d6b463842d00b958d953b2f6d5c59701286f3b2d6344d5b556fba  analyze_laguna_m8_actual_offline_gate.py
1f491cd89a8659c05c9d5668c2c978ade3b2e98fc61d299977f196130522cf01  capture_laguna_m8_idle_snapshot.py
f28a096aeafafae44bb3d57b789dc8c00942a3f44da57d3c2a4935b16e5ca0d3  run_laguna_m8_actual_offline.py
73ba1169bf8b44ca34287e3711fd34b8a73c6247ab6856773e49a676d493bf08  run_laguna_m8_actual_offline_gate.sh
f8c4ee57304ba7578fc7ea577d15e0f5e123c03df4b92cb923ef46ffe72fed31  test_analyze_laguna_m8_actual_offline_gate.py
```

The launcher separately pins the four installed kernel binaries, oneCCL,
SYCL, Level Zero driver, and Level Zero loader by SHA-256. Target and draft
model contents must pass the retained 118-file NVMe manifest before any arm.
The external Corsair USB is forbidden for model reads, cache, temp, RPC,
logs, or evidence.

## Fresh short RPC identity

The following exact directories were confirmed absent before this
preregistration and are one-shot state:

```text
incumbent-eager  /mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/tmp/m8p2-a
segmented-eager  /mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/tmp/m8p2-b
segmented-graph  /mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/tmp/m8p2-c
```

The launcher must create each canonical directory mode `0700` on
`/dev/nvme0n1p2` ext4, set it explicitly as `VLLM_RPC_BASE_PATH` under
`env -i`, and seal every directory after success or failure. The driver binds
the exact directory to its arm and records it; the analyzer rejects any
mapping or environment drift. With vLLM's slash plus 36-byte UUID, each
AF_UNIX filesystem path is exactly 100 bytes. The gate caps this at 100,
below this platform's pyzmq limit of 107. The private per-arm `TMPDIR` and
cache layout is otherwise unchanged.

## Arms and required evidence

All three arms retain the exact configuration from the first
preregistration: TP4/EP4, BF16 KV, exact M8 attention/MoE, record kernel
stack, greedy DFlash depth 7 with standard rejection, no prefix cache, no
async scheduling, no warm-up, and one 32-token `ignore_eos=true` generation.

1. `incumbent-eager`: canonical incumbent eager target.
2. `segmented-eager`: persistent eager buffers at all 97 target collectives.
3. `segmented-graph`: target-only M=8 Breakable graph capture/replay; drafter
   eager and logits outside the wrapper.

Arm A is canonical. There is no majority vote. Every rank must provide at
least four eligible target events. The final analyzer re-reads and hashes all
manifests, sidecars, and raw tensor bytes and requires exact event-by-event
A/B/C identity for logical request keys, all 48 attention Q/K/V/O tensors and
slot signatures, target hidden state and live inputs, sampled/proposed/
accepted/emitted tokens, and final driver token IDs. B/C must also prove all
97 collective outputs/local inputs. C must prove one descriptor, one capture,
146 graph segments, 145 eager breaks, and monotonically numbered replays.
All arms must report `num_cached_tokens=0`.

Physical backend-owned KV packing remains explicitly unsupported by this
component recorder. A later endpoint candidate must still pass the canonical
q=1 greedy teacher, cross-start, cache-zero, long-then-next, and 863-token
rollover gates.

## Stop and continuation rules

- Any path, reuse, permission, worker, XPU-idle, model-content, source,
  binary, environment, process, timeout, manifest, sidecar, raw-byte,
  event-order, graph, acceptance, usage, cache, or token mismatch fails
  closed.
- This root and all three RPC directories are never reused. An operational
  failure requires another committed correction and preregistration. A raw
  mismatch closes this segmented graph identity.
- No timing, speed, endpoint, record, or submission claim can result from
  this gate.
- A pass authorizes only a separately preregistered PTI/component-timing lane.
  Endpoint and canonical teacher verification remain mandatory after that.

## Pre-execution validation and exact launch

Before this registration, the corrected main-repo suite passed 10 tests, the
reviewed vLLM recorder suite passed 10 tests, Ruff, formatting, Python
compilation, shell syntax, and diff checks passed, and a direct source check
confirmed a 100-byte AF_UNIX path. An independent read-only Terra audit found
no launch blocker and confirmed there is no `TMPDIR` fallback. No model/XPU
work was used for these checks.

The only authorized launch is:

```bash
/usr/bin/env -i \
  PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  /usr/bin/bash \
  /home/steve/llm-optimizations/experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_m8_actual_offline_gate.sh \
  /mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-actual-offline-820d827a3-20260724T161333Z
```
