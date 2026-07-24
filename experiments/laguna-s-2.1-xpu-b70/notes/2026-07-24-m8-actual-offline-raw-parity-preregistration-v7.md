# Laguna M8 actual-model offline raw-parity preregistration v7

Date: 2026-07-24 America/Toronto

## Purpose and terminal predecessor

This preregisters one fresh private-NVMe, offline, nonbenchmark A/B/C
correctness gate for the actual Laguna S 2.1 target M=8 verifier. Each arm gets
exactly one `LLM.generate` call in a fresh process. Raw parity must pass before
trace, timing, endpoint, benchmark, payload, or LocalMaxxing work.

The v6 root is terminal, sealed, and never reused:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-actual-offline-b0174430b-20260724T174418Z
```

Its A arm passed the corrected exact 54-key target-plus-DFlash map, returned
one cache-zero generation, and aggregated 60 rank-forward records / 12,060 raw
events. It then failed while writing `driver.json` because vLLM had mutated
the caller's speculative-config dict with a non-JSON `ModelConfig`. B/C did
not start and the returned token list was not persisted. Preserve:

- `experiments/laguna-s-2.1-xpu-b70/notes/2026-07-24-m8-actual-offline-driver-config-serialization-abort.md`;
- `data/laguna-m8-actual-offline-driver-config-serialization-abort-20260724.json`.

The approved record remains `33.89498511171744 tok/s`, LocalMaxxing
`cmrx6p5dv001bo4017hb7sixz`.

## Frozen identity

- corrected main-repo tooling:
  `b601b7c5efd19cde1a003b67fe8b11ec3f9e29f6`;
- immutable-config implementation ancestor:
  `13af8656e`;
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
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-actual-offline-b601b7c5e-20260724T180806Z`.

Tool SHA-256:

```text
a3c27e621e318d0ce3b094cc0882d017f739503694d04db3b33f88bb322231f1  analyze_laguna_m8_actual_offline_gate.py
1f491cd89a8659c05c9d5668c2c978ade3b2e98fc61d299977f196130522cf01  capture_laguna_m8_idle_snapshot.py
99ea295ad3432c5b66aab91a4319f1d6bec827883548be7d10d5d1f77bf01e55  laguna_nvme_paths.sh
dd88b889075fda00c1d3da39be59d715eed46d0887cc053e05c1e9694a69c5bc  run_laguna_m8_actual_offline.py
935f1f2f679d2d77e6b3ef9e4c3dec0e4760c240c1b2e4797a300690883c1a3d  run_laguna_m8_actual_offline_gate.sh
473f032e0fba89c64f2939497cf5dc507dcf3203f957a0f8eece2a83e491e204  test_analyze_laguna_m8_actual_offline_gate.py
```

Installed runtime/kernel binaries and the 118-file target/draft manifest remain
pinned. The external Corsair USB remains forbidden for active model, cache,
temp, RPC, log, or evidence paths.

## Immutable config-evidence correction

Before constructing `LLM`, the driver serializes engine, speculative, and
compilation configurations into one canonical sorted JSON string with
`allow_nan=false`. A detached decode supplies runtime kwargs. After generation
and aggregation, a second decode of the immutable original string supplies
the driver record.

Therefore vLLM may mutate its detached runtime speculative dictionary without
altering or making the evidence record unserializable. Eager
`compilation_config=null` remains omitted from the `LLM` call; graph retains
the exact frozen dictionary. The regression test injects non-JSON runtime
objects and nested mutations and proves the recorded copy stays independent.
No model-execution code or arithmetic changed.

The exact-slot observer still requires 48 target plus 6 DFlash mappings on
`xpu:<TP rank>`, validates int64 `[8]` stride `[1]`, and serializes only the
ordered target 0-47 vector.

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
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/tmp/m8p7-a
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/tmp/m8p7-b
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/tmp/m8p7-c
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

The complete related vLLM CPU suite passed 73 tests and the evidence-focused
suite passed 25. The main analyzer/driver suite passed 17 tests plus five
subtests. Ruff, formatting, shell syntax, diff, config-isolation, exact-slot,
identity, NVMe, and stale-literal checks passed. Independent audits found no
blocker. No model or XPU work was used for patch validation.

The only authorized launch is:

```bash
/usr/bin/env -i \
  PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  /usr/bin/bash \
  /home/steve/llm-optimizations/experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_m8_actual_offline_gate.sh \
  /mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-actual-offline-b601b7c5e-20260724T180806Z
```
