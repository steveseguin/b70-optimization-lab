# Laguna M8 actual-model offline raw-parity preregistration v10

Date: 2026-07-24 America/Toronto

## Purpose and terminal predecessor

This preregisters one fresh private-NVMe, offline, nonbenchmark A/B/C
correctness gate for the actual Laguna S 2.1 target M=8 verifier. Each arm gets
exactly one `LLM.generate` call in a fresh process. Raw parity must pass before
trace, timing, endpoint, benchmark, payload, or LocalMaxxing work.

The v9 root is terminal, sealed, and never reused:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-actual-offline-4f93bd939-20260724T192555Z
```

All three arms completed with cache zero and clean post-idle proof. A and B
were bitwise identical. C captured once and replayed thereafter, but its first
live capture consumed a zero, unmaterialized embedding graph-segment output
before the embedding all-reduce. C emitted token `0` where canonical B emitted
`19`, produced a different final token/text hash, and failed closed. Preserve:

- `experiments/laguna-s-2.1-xpu-b70/notes/2026-07-24-m8-actual-offline-live-capture-unmaterialized-segment-failure.md`;
- `data/laguna-m8-actual-offline-live-capture-unmaterialized-segment-failure-20260724.json`.

The approved record remains `33.89498511171744 tok/s`, LocalMaxxing
`cmrx6p5dv001bo4017hb7sixz`.

## Frozen identity

- corrected main-repo tooling:
  `1cc59f68afb32f88eb63b9b7092792a16a2b62c3`;
- materialized live-capture vLLM:
  `439975d5ae6535553c5d846a2393b0da514447e3`;
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
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-actual-offline-1cc59f68a-20260724T201926Z`.

Tool SHA-256:

```text
43526f74042d221b75895dc4760bf6664c32a51b247d317c13bcc941ce3a46fa  analyze_laguna_m8_actual_offline_gate.py
1f491cd89a8659c05c9d5668c2c978ade3b2e98fc61d299977f196130522cf01  capture_laguna_m8_idle_snapshot.py
99ea295ad3432c5b66aab91a4319f1d6bec827883548be7d10d5d1f77bf01e55  laguna_nvme_paths.sh
e06c27756f6c3c4edb2b3b6015c1629affbea7e97c34392aecfb9fea95f74ab2  run_laguna_m8_actual_offline.py
a7a8d530445cbccebd2185187f40e43a996fab1908ab778aa43a3aa8672f8c3d  run_laguna_m8_actual_offline_gate.sh
afe82fc721162d32a7ddb7eb746d32c5ddf09384c603e5549dcc8e0908b1c8a1  test_analyze_laguna_m8_actual_offline_gate.py
```

Installed runtime/kernel binaries and the 118-file target/draft manifest remain
pinned. The external Corsair USB remains forbidden for active model, cache,
temp, RPC, log, or evidence paths.

## First-live segment materialization correction

CUDA graph kernels are recorded but not executed during capture. Generic
Breakable capture retains that behavior. Only the already guarded Laguna M=8
wrapper opts into first-live segment materialization:

1. ending a captured graph segment stores its replay callable exactly as
   before;
2. before the following eager collective or attention boundary runs, that new
   graph segment is replayed once so its output buffer is real;
3. after the final segment is recorded, it is replayed once before the live
   wrapper returns;
4. if the capture body raises, the final segment is closed but not executed;
5. subsequent eligible calls use the unchanged stored graph/eager sequence.

This causes each graph segment and eager boundary to execute exactly once for
the live capture transaction. Calling the entire capture replay after capture
would be wrong because it would execute all 145 eager boundaries twice,
duplicate KV/collective side effects, and double evidence counters.

The existing exact eligibility predicate, runtime capture-monitor scope,
wrapper defense-in-depth filter, fixed input identities, 146/145 topology,
one-capture rule, evidence, collectives, arithmetic, sampling, model weights,
and kernel binaries remain unchanged. The driver and aggregate schemas advance
to `laguna-m8-offline-arm-v10` and
`laguna-m8-actual-offline-gate-v11`.

## Arms, fresh paths, and stop rules

All arms retain the approved BF16-KV DFlash-depth-7 TP4/EP4 stack, exact
attention/MoE, record fusions, W1 N64, standard rejection, greedy draft, no
prefix cache, no async scheduling, no warm-up, and one 32-token
`ignore_eos=true` generation.

1. A: canonical true eager, segmentation/graph off.
2. B: true eager with persistent collective-boundary buffers.
3. C: compilation `NONE`, PIECEWISE capture `[8]`, target-only Breakable
   capture/replay with live segment materialization; draft and logits eager.

Fresh one-shot RPC bases use `a` as the hexadecimal successor to v9 while
preserving the exact 100-byte conservative UUID socket path:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/tmp/m8pa-a
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/tmp/m8pa-b
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/tmp/m8pa-c
```

The root and RPC bases were confirmed absent. Each base must be newly created
canonical mode `0700` on `/dev/nvme0n1p2` ext4.

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

The focused runtime suite passed 65 tests with 11 device-only CUDA skips.
Those tests include device-free graph/eager ordering and exception cleanup,
plus the existing eligibility, monitor, raw-evidence, and collective
contracts. Ruff and formatting passed. The main analyzer and operational
preflight suites passed 36 tests and 38 subtests. Shell syntax, diff, identity,
NVMe path length/absence, and stale-active-literal checks passed. Independent
raw-artifact and source audits agreed on the unmaterialized first-segment root
cause and the per-segment correction. No model or XPU work was used for patch
validation.

The only authorized launch is:

```bash
/usr/bin/env -i \
  PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  /usr/bin/bash \
  /home/steve/llm-optimizations/experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_m8_actual_offline_gate.sh \
  /mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-actual-offline-1cc59f68a-20260724T201926Z
```
