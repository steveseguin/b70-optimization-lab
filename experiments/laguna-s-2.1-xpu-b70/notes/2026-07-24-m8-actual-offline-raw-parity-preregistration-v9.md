# Laguna M8 actual-model offline raw-parity preregistration v9

Date: 2026-07-24 America/Toronto

## Purpose and terminal predecessor

This preregisters one fresh private-NVMe, offline, nonbenchmark A/B/C
correctness gate for the actual Laguna S 2.1 target M=8 verifier. Each arm gets
exactly one `LLM.generate` call in a fresh process. Raw parity must pass before
trace, timing, endpoint, benchmark, payload, or LocalMaxxing work.

The v8 root is terminal, sealed, and never reused:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-actual-offline-872c304f8-20260724T184608Z
```

Arms A and B completed, each with cache zero, identical 32-token API output,
complete driver/aggregate evidence, and clean post-idle proof. C completed
generic startup graph warmup but failed on its first intended live M=8 lazy
capture because `capture_model()` had disabled the global capture monitor.
Preserve:

- `experiments/laguna-s-2.1-xpu-b70/notes/2026-07-24-m8-actual-offline-runtime-capture-monitor-abort.md`;
- `data/laguna-m8-actual-offline-runtime-capture-monitor-abort-20260724.json`.

The approved record remains `33.89498511171744 tok/s`, LocalMaxxing
`cmrx6p5dv001bo4017hb7sixz`.

## Frozen identity

- corrected main-repo tooling:
  `4f93bd939cfc52311162200e63119da391184195`;
- guarded runtime-capture vLLM:
  `7e674bfbd05100383dc9e949f813fa7483b53cc3`;
- approved-record vLLM ancestor:
  `8936aac144929190c1e53f8b8624ca397ce16f5b`;
- approved-record XPU-kernel ancestor:
  `b6076ce1249ffee0e30bee528f4cd15c3bffb234`;
- frozen kernel descendant:
  `4772f727590c51b72add79350b913d098cf67872`;
- target revision:
  `4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb`;
- DFlash revision:
  `5e07c246915c86dc6920fead03d019989224f2ba`;
- exact fresh run root:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-actual-offline-4f93bd939-20260724T192555Z`.

Tool SHA-256:

```text
a9edc75ea52202fc5bfcb7fbdf12fc6ddf4a3599a6d4f5ecef626f3d29e5f497  analyze_laguna_m8_actual_offline_gate.py
1f491cd89a8659c05c9d5668c2c978ade3b2e98fc61d299977f196130522cf01  capture_laguna_m8_idle_snapshot.py
99ea295ad3432c5b66aab91a4319f1d6bec827883548be7d10d5d1f77bf01e55  laguna_nvme_paths.sh
e4af56acbf421ea58544ff07817941d3fef55f0647bbc5fc8bc7a540d8b2c19b  run_laguna_m8_actual_offline.py
37ed530cda6a47c177b15ce567230f29da92a0b7eb8efac717cb8156aa08ee5d  run_laguna_m8_actual_offline_gate.sh
afe82fc721162d32a7ddb7eb746d32c5ddf09384c603e5549dcc8e0908b1c8a1  test_analyze_laguna_m8_actual_offline_gate.py
```

Installed runtime/kernel binaries and the 118-file target/draft manifest remain
pinned. The external Corsair USB remains forbidden for active model, cache,
temp, RPC, log, or evidence paths.

## Guarded first-live capture correction

Startup dummy capture remains filtered out because it is not a real exact
speculative-verifier transaction. The first live target forward is admitted
only if the existing fail-closed predicate proves all of the following:

- Laguna breakable graph is explicitly enabled;
- one request and exactly eight target rows;
- exactly seven DFlash speculative tokens;
- PIECEWISE descriptor size 8;
- no encoder input, LoRA, cascade attention, scale calculation, or ubatching;
- TP4/EP4, depth 7, standard rejection, greedy draft, compile mode NONE.

Only around that guarded target `_model_forward`, the runner enables the
capture monitor. A `finally` block restores disabled state after either
success or exception. The Breakable wrapper independently rechecks PIECEWISE,
M=8, exact-spec, and eligibility before capture. Later eligible calls find the
same descriptor and replay; all noneligible runtime captures remain rejected.
The drafter and logits stay outside the scope.

No arithmetic, sampling, raw-evidence, model weights, or kernel binary changed.
The driver and aggregate schemas advance to
`laguna-m8-offline-arm-v9` and `laguna-m8-actual-offline-gate-v10`.

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
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/tmp/m8p9-a
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/tmp/m8p9-b
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/tmp/m8p9-c
```

The root and RPC bases were confirmed absent. Each UUID socket path is exactly
100 bytes and each base must be newly created canonical mode `0700` on
`/dev/nvme0n1p2` ext4.

The analyzer requires complete A/B/C driver and raw evidence, exactly 32
returned token IDs, cache-zero, exact logical/live target routing and raw
tensors, 97 B/C collectives, and C's one capture followed by replay topology.
Any identity, path, reuse, permission, worker, idle, model, source, binary,
environment, process, timeout, serialization, raw-byte, graph, usage, cache,
or token mismatch fails closed. The root and RPC paths are never reused.

This component gate cannot produce a speed, record, payload, or submission
claim. A later endpoint must still pass canonical q1 teacher, cross-start,
cache-zero, long-then-next, and rollover gates.

## Validation and only authorized launch

The relevant vLLM CPU suite passed 93 tests with 10 platform skips; the direct
Laguna worker subset passed 25. Ruff, formatting, shell syntax, main
analyzer/driver tests (19), operational preflight tests (17), diff, identity,
NVMe, and stale-literal checks passed. Three generic custom-op expectations
outside this change fail under the installed XPU policy because Inductor is
disabled; they are unrelated and recorded rather than counted as passes.
Independent review found no blocker and confirmed exception-safe monitor
restoration. No model or XPU work was used for patch validation.

The only authorized launch is:

```bash
/usr/bin/env -i \
  PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  /usr/bin/bash \
  /home/steve/llm-optimizations/experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_m8_actual_offline_gate.sh \
  /mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-actual-offline-4f93bd939-20260724T192555Z
```
