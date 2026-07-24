# Laguna M8 actual-model offline raw-parity preregistration v6

Date: 2026-07-24 America/Toronto

## Purpose and terminal predecessor

This preregisters one fresh private-NVMe, offline, nonbenchmark A/B/C
correctness gate for the actual Laguna S 2.1 target M=8 verifier. Each arm gets
exactly one `LLM.generate` call in a fresh process. Raw parity must pass before
any trace, timing, endpoint, benchmark, payload, or LocalMaxxing action.

The v5 root is terminal, sealed, and never reused:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-actual-offline-598dc430d-20260724T172414Z
```

Its A arm reached the first M=8 evidence hook and deterministically failed
before any recorded event because the observer required the global
`slot_mappings` dictionary to contain only 48 target keys. With DFlash loaded,
the dictionary correctly contains 48 target plus 6 draft keys. `LLM.generate`
did not return, B/C did not start, cleanup and idle passed, and no result was
produced. Preserve:

- `experiments/laguna-s-2.1-xpu-b70/notes/2026-07-24-m8-actual-offline-target-plus-draft-slot-abort.md`;
- `data/laguna-m8-actual-offline-target-plus-draft-slot-abort-20260724.json`.

The approved record remains `33.89498511171744 tok/s`, LocalMaxxing
`cmrx6p5dv001bo4017hb7sixz`.

## Frozen identity

- corrected main-repo tooling:
  `b0174430bc10add179f210c6990516995d852265`;
- approved-record vLLM ancestor:
  `8936aac144929190c1e53f8b8624ca397ce16f5b`;
- reviewed recorder, graph diagnostic, DFlash unwrap, and exact-slot vLLM:
  `e25867aa698f82cbf2fb835e26807078674acebc`;
- approved-record XPU-kernel ancestor:
  `b6076ce1249ffee0e30bee528f4cd15c3bffb234`;
- frozen kernel descendant:
  `4772f727590c51b72add79350b913d098cf67872`;
- target revision:
  `4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb`;
- DFlash revision:
  `5e07c246915c86dc6920fead03d019989224f2ba`;
- exact fresh run root:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-actual-offline-b0174430b-20260724T174418Z`.

Tool SHA-256:

```text
dd9329dbfa7e70a592a75f0888cc442bfdcbcc3b4dfc3e6818ba2e9213088b46  analyze_laguna_m8_actual_offline_gate.py
1f491cd89a8659c05c9d5668c2c978ade3b2e98fc61d299977f196130522cf01  capture_laguna_m8_idle_snapshot.py
99ea295ad3432c5b66aab91a4319f1d6bec827883548be7d10d5d1f77bf01e55  laguna_nvme_paths.sh
49e49d98146f0ed30930795878ae95887665ec30429d860d882251f1353cdf1b  run_laguna_m8_actual_offline.py
f080471ccb43b8c1a04b32d0a60985e4cb6f59731bf889b3ec58210b35fc0e4e  run_laguna_m8_actual_offline_gate.sh
40d092daf3d5ddb6123abfbfb948accf7afd856ae3561fe4033d65f0276c77ad  test_analyze_laguna_m8_actual_offline_gate.py
```

The launcher pins the installed kernel/runtime binaries and verifies the
118-file target/draft manifest. The external Corsair USB is forbidden for
active model, cache, temp, RPC, log, or evidence paths.

## Corrected evidence contract

The runtime requires the complete exact KV mapping allowlist:

```text
model.layers.0..47.self_attn.attn   target
model.layers.48..53.self_attn.attn  DFlash draft
```

All 54 mappings must be tensors on `xpu:<TP rank>` with dtype int64, shape
`[8]`, and stride `[1]`. Unknown, missing, renamed, malformed, or wrong-device
target or draft mappings fail before evidence acceptance. Shared tensor
identities are hashed once. Only the 48 target signatures are copied into the
ordered logical vector; draft signatures cannot leak.

The analyzer independently binds each target layer's four live Q/K/V/O
signatures to that logical vector and compares complete live routing across
A/B and B/C. Evidence-off execution and all model arithmetic remain
unchanged.

## Arms, fresh paths, and stop rules

All arms retain the approved BF16-KV DFlash-depth-7 stack: TP4/EP4, exact
attention/MoE, fused W1-route-W2, route-interleaved W2, W1 N64,
shared-elementwise and QKNorm/RoPE fusions, standard rejection, greedy draft,
no prefix cache, no async scheduling, no warm-up, and one 32-token
`ignore_eos=true` generation.

1. A: true eager, segmentation and graph off; canonical.
2. B: true eager with persistent collective-boundary buffers.
3. C: compilation mode `NONE`, PIECEWISE capture `[8]`, target-only Breakable
   capture/replay; draft and logits remain eager.

The fresh one-shot RPC bases are:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/tmp/m8p6-a
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/tmp/m8p6-b
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/tmp/m8p6-c
```

They and the run root were confirmed absent. Each UUID socket path is exactly
100 bytes, within the frozen conservative limit, and each base must be newly
created canonical mode `0700` on `/dev/nvme0n1p2` ext4.

Every rank must expose at least four eligible events. The analyzer re-hashes
every artifact and requires exact A/B/C logical keys, all 48 target attention
Q/K/V/O tensors and routing, hidden states and real inputs,
sample/proposal/acceptance/emitted IDs, final tokens, cache-zero, 97 B/C
collectives, and C's one capture plus 146 segments/145 eager breaks.

Any identity, path, reuse, permission, worker, idle, model, source, binary,
environment, process, timeout, raw-byte, graph, usage, cache, or token mismatch
fails closed. The root and RPC paths are never reused. This component gate
cannot produce a speed, record, payload, or submission claim. Any later
endpoint must still pass canonical q1 teacher, cross-start, cache-zero,
long-then-next, and rollover gates.

## Validation and only authorized launch

The complete related vLLM CPU-only suite passed 73 tests; the evidence-focused
suite passed 25. The main analyzer passed 16 tests plus five subtests. Ruff,
formatting, shell syntax, diff, identity, topology, device, malformed-draft,
and tensor-hash caching checks passed. Independent read-only audits found no
blocker. No model or XPU work was used for patch validation.

The only authorized launch is:

```bash
/usr/bin/env -i \
  PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  /usr/bin/bash \
  /home/steve/llm-optimizations/experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_m8_actual_offline_gate.sh \
  /mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-actual-offline-b0174430b-20260724T174418Z
```
