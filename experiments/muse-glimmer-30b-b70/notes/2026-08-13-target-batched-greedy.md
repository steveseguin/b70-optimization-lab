# Target batched device-greedy verification

Date: 2026-08-13

## Result

This is a retained exact inference-path win. Offloading all target verifier
rows to one batched, distributed device ARGMAX raised the fixed-suite mean
from pooled adjacent controls of `73.109 tok/s` to `77.824 tok/s`, or
`+6.449%`. No drafter training or weight change was involved.

| Arm | Prose | Code | JSON | Mean tok/s |
| --- | ---: | ---: | ---: | ---: |
| device-DFlash control before | 51.874 | 75.509 | 91.735 | 73.039 |
| target + DFlash device greedy | 54.944 | 81.148 | 97.381 | 77.824 |
| device-DFlash control after | 52.231 | 75.446 | 91.861 | 73.179 |

All three candidate outputs matched the canonical hashes:

- prose `914f754747d0edaa`;
- code `cf2b2c4fd9e36fe5`;
- JSON `4f813a9706abc163`.

Candidate drafted/accepted counts were `1199/172`, `796/198`, and `684/207`.
The controls were `1198/172, 811/197, 684/207` before and
`1199/172, 811/197, 684/207` after. Therefore the output identity is exact,
but the code row includes the familiar one-token proposal-history variation;
the result is not presented as a pure kernel-time delta. Derived round time
still falls consistently by roughly `3.3-3.5 ms` in prose and JSON, whose
accepted counts match exactly.

## Why the earlier retry was misclassified

The earlier target-backend-sampling attempt did not enable
`LLAMA_BACKEND_GREEDY_BATCH_ROWS=1`. Its first prompt row completed one global
ARGMAX, then its 16-row speculative verification graph took the unbatched
path. The connection closed before a result, and the negative note inferred
that speculative verification required raw logits.

Reopening the lane exposed a different, reproducible cause: a CPU segfault in
`ggml_backend_meta_graph_compute` while rebuilding retained simple-backend
graphs. A symbolized `libggml-base` localized it to the write to
`cgraph_ij->nodes` at `ggml-backend-meta.cpp:2179`.

Two independent high-water lifetime bugs were fixed:

1. retained simple graphs are now created with `max_nnodes`, not the current
   graph's node count (`acd456b8c`);
2. replacing the graph arena now recreates every slot through
   `max_subgraphs`, not only the current topology's subgraphs (`380177482`).

The second bug was the immediate null/stale-pointer cause: a topology could
raise the node high-water mark while using fewer subgraphs, resetting the
arena and leaving higher graph slots invalid. A later 16-row topology could
grow back within the existing subgraph high-water mark without triggering
another allocation.

After both fixes, the eight-token smoke completed at
`52.927 / 134.560 / 133.900 tok/s`; its 100% short-block acceptance makes that
only a functional proof, not a century result. The full 256-token C/A/C above
is the performance authority.

## Identity and gates

- target: Muse Glimmer 30B BF16, TP4, tensor split;
- assistant: BF16 DFlash, width 15, `p_min=0`;
- greedy, parallel 1, cache off, 256 tokens per fixed prompt;
- retained oneDNN caches, shared BF16 conversion, parallel meta submit;
- retained DFlash batched device greedy and local-winner maxloc;
- candidate additionally uses target `--backend-sampling` with an explicit
  terminal temperature/greedy chain;
- target and DFlash both use the same batched 16-row TP maxloc path.

The path remains default-off and is only valid for backend-compatible greedy
sampling (no grammar or requested probability payloads). Generic CPU sampling
remains the fallback.

## Evidence

- smoke config:
  `sweeps/20260813-target-batched-greedy-smoke.json`;
- C/A/C config:
  `sweeps/20260813-target-batched-greedy-final-cac.json`;
- smoke JSONL SHA256:
  `252db1b69e08c42460a72786978ac4db4e2f922ebac6601047cd1a1365c78c9a`;
- full C/A/C JSONL SHA256:
  `a746aa810c9c0fedd8793a0980f8fd0b3f7d316577bc275719b54740c88cd69c`;
- final smoke server log SHA256:
  `025b89d7026ad1594d95cab16a4c91d7e3685df79d3718d8fa093d0d1b866ebe`.

Raw files are under
`/mnt/fast-ai/bench-results/muse-glimmer-30b/{sweeps,servers}/`.
Production was restored without reboot and passed the full model,
cache-zero/code, and vision gate in
`data/muse-health-20260813-target-batched-greedy-final-restore.json`.

## Decision

Promote `77.824 tok/s` as the new exact TP4 campaign best. The `>100 tok/s`
goal remains unmet. This result removes about `3.4 ms` per speculative round;
the remaining gap still requires a larger verifier or acceptance lever rather
than another tiny sampling-copy optimization.

## Follow-up: attention batch=2 allocator screen

A bounded follow-up tried to unlock the existing Q+attention-gate and K+V
oneDNN batch=2 implementation by marking the later gate and V projection
outputs as graph outputs, preventing ordinary arena reuse. This did not make
either pair legal in the TP simple graphs. The proof log still reported:

- Q+gate `batch-stride-span`: the per-rank pointer gap was smaller than one
  projection output;
- K+V `output-alias`: both per-rank outputs retained the same address.

The target meta compute reservation also grew from about `486 MiB` to
`1353 MiB`, so retaining all 52 layers' outputs is not an acceptable allocator
strategy even if the simple-tensor mapping were changed. No first-hit marker
appeared. The model change was reverted; the existing strict overlap guards
remain intact. The eight-token output smoke completed, but its rates are not a
performance result because the experimental GEMMs never executed.

Evidence:

- config: `sweeps/20260813-attn-batch2-alloc-smoke.json`;
- JSONL SHA256:
  `9f0925914a453f40921812168f9ee04df4e782d38bd0a1c50a9ac4b5aadf898f`;
- server log SHA256:
  `037bfb36f6a80506d40d99826a3d313e2dd44ad6488782a8e4cf060f1f3a9479`;
- restore gate:
  `data/muse-health-20260813-attn-batch2-alloc-restore.json`.
