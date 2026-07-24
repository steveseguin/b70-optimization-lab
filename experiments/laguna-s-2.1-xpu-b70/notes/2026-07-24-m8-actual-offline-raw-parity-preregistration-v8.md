# Laguna M8 actual-model offline raw-parity preregistration v8

Date: 2026-07-24 America/Toronto

## Purpose and terminal predecessor

This preregisters one fresh private-NVMe, offline, nonbenchmark A/B/C
correctness gate for the actual Laguna S 2.1 target M=8 verifier. Each arm gets
exactly one `LLM.generate` call in a fresh process. Raw parity must pass before
trace, timing, endpoint, benchmark, payload, or LocalMaxxing work.

The v7 root is terminal, sealed, and never reused:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-actual-offline-b601b7c5e-20260724T180806Z
```

Arm A completed with cache zero, a durable 32-token driver record, and
validated aggregate evidence. Arm B completed generation and wrote 60
complete raw manifests, but the stale analyzer expected `full_topology` at
event 437 instead of its runtime position at event 439. Arm C did not start.
Preserve:

- `experiments/laguna-s-2.1-xpu-b70/notes/2026-07-24-m8-actual-offline-segmented-eager-label-order-abort.md`;
- `data/laguna-m8-actual-offline-segmented-eager-label-order-abort-20260724.json`.

After the exact analyzer repair, all 60 immutable B manifests revalidated and
the strict A/B raw evidence comparison passed on all four ranks and all 15
eligible events per rank. Because B did not persist its final driver record
before the v7 failure, the predecessor remains non-promotable.

The approved record remains `33.89498511171744 tok/s`, LocalMaxxing
`cmrx6p5dv001bo4017hb7sixz`.

## Frozen identity

- corrected main-repo tooling:
  `872c304f8d581025f57aef4abee7f408918cffd8`;
- runtime-order analyzer implementation ancestor:
  `acfadc521`;
- approved-record vLLM ancestor:
  `8936aac144929190c1e53f8b8624ca397ce16f5b`;
- reviewed recorder/graph/DFlash exact-slot vLLM:
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
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-actual-offline-872c304f8-20260724T184608Z`.

Tool SHA-256:

```text
34c01f2c404b7c3ba3460c46ef7307f299456822a89cc79417ff5dac8c38c55b  analyze_laguna_m8_actual_offline_gate.py
1f491cd89a8659c05c9d5668c2c978ade3b2e98fc61d299977f196130522cf01  capture_laguna_m8_idle_snapshot.py
99ea295ad3432c5b66aab91a4319f1d6bec827883548be7d10d5d1f77bf01e55  laguna_nvme_paths.sh
a17e5c1eb519eeb0678be6ffc4e5f8af5d27674d90c03a2b9fd2c8993f7fd9c1  run_laguna_m8_actual_offline.py
e9a81a106ce14a3ad5e80a0f3bf50b4b53d85b7b3970320b47093ba20a9e1220  run_laguna_m8_actual_offline_gate.sh
afe82fc721162d32a7ddb7eb746d32c5ddf09384c603e5549dcc8e0908b1c8a1  test_analyze_laguna_m8_actual_offline_gate.py
```

Installed runtime/kernel binaries and the 118-file target/draft manifest remain
pinned. The external Corsair USB remains forbidden for active model, cache,
temp, RPC, log, or evidence paths.

## Exact runtime-order correction

The analyzer still requires exact equality of the complete event-label stream.
Only its expected lifecycle is corrected:

```text
... final all_gather
target_hidden_before_logits
kv_capture_status
full_topology
logits_boundary
sampled_token_ids_after_logits
spec_acceptance_before_bookkeeping
emitted_ids_after_bookkeeping
```

This matches the reviewed producer: the runner records hidden and KV status
after model forward, then `finish_eligible_forward()` emits topology before
logits. Capture/replay still records the phase-specific
`breakable_{capture,replay}_topology` before this common tail. Synthetic
fixtures now match that lifecycle, and negative tests swap `full_topology`
with each adjacent metadata event and require a label-order rejection. No
model-execution code, arithmetic, raw format, or runtime commit changed.

The driver and aggregate schemas advance to
`laguna-m8-offline-arm-v8` and `laguna-m8-actual-offline-gate-v9`.

## Arms, fresh paths, and stop rules

All arms retain the approved BF16-KV DFlash-depth-7 TP4/EP4 stack, exact
attention/MoE, record fusions, W1 N64, standard rejection, greedy draft, no
prefix cache, no async scheduling, no warm-up, and one 32-token
`ignore_eos=true` generation.

1. A: canonical true eager, segmentation/graph off.
2. B: true eager with persistent collective-boundary buffers.
3. C: compilation `NONE`, PIECEWISE capture `[8]`, target-only Breakable
   capture/replay; draft and logits eager.

Fresh one-shot RPC bases:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/tmp/m8p8-a
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/tmp/m8p8-b
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/tmp/m8p8-c
```

The root and RPC bases were confirmed absent. Each UUID socket path is exactly
100 bytes and each base must be newly created canonical mode `0700` on
`/dev/nvme0n1p2` ext4.

The analyzer requires complete A/B/C driver and raw evidence, exactly 32
returned token IDs, cache-zero, exact logical/live target routing and raw
tensors, 97 B/C collectives, and C's capture/replay topology. Any identity,
path, reuse, permission, worker, idle, model, source, binary, environment,
process, timeout, serialization, raw-byte, graph, usage, cache, or token
mismatch fails closed. The root and RPC paths are never reused.

This component gate cannot produce a speed, record, payload, or submission
claim. A later endpoint must still pass canonical q1 teacher, cross-start,
cache-zero, long-then-next, and rollover gates.

## Validation and only authorized launch

The main analyzer/driver suite passed 19 tests and the operational preflight
suite passed 17 tests. Shell syntax, diff, immutable real-manifest
revalidation, strict sealed A/B comparison, identity, NVMe, and stale-literal
checks passed. Independent audits found no blocker. No model or XPU work was
used for patch validation.

The only authorized launch is:

```bash
/usr/bin/env -i \
  PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  /usr/bin/bash \
  /home/steve/llm-optimizations/experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_m8_actual_offline_gate.sh \
  /mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-actual-offline-872c304f8-20260724T184608Z
```
