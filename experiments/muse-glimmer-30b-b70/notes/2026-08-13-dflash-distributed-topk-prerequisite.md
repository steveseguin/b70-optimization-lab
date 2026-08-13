# DFlash distributed top-k: retained tree prerequisite

Date: 2026-08-13

## Decision

Retain source commit `d5e9a2734` as a default-off inference-path primitive.
It exports the top 15 candidates, logits, and probabilities for all 16 DFlash
rows without copying the full TP-sharded vocabulary to the host. No drafter
training was performed.

This is a prerequisite for same-width budget-15 DDTree, not a century result.
The device-top15 trace projects only **94.108 tok/s** at zero tree-bookkeeping
cost and still needs **3.194 ms per speculation round** of uniform exact
savings to reach 100.

## Implementation

The DFlash-only backend sampler builds one batched `TOP_K(k=15)` over all
proposal rows, gathers the selected F32 values, computes the truncated softmax,
and exposes per-row sampled IDs, probabilities, logits, and candidate IDs.

For TP2/TP4, the meta backend recognizes only the exact named DFlash sampler
dataflow. Each device computes its local top-k; the SYCL communicator packs
`(value, global_id)`, performs a tiny peer all-gather, and merges the global
top-k on every rank. Prevalidation failures use a synchronous host fallback.
Once device submission begins, a synchronous exception is fatal: falling back
after partially globalizing indices would be corrupt.

The path also hardens the existing SYCL local top-k so `-inf` and exact
`-FLT_MAX` values still receive valid unique indices. It uses a defined order:
finite values before NaNs, descending value, then descending token ID; NaNs are
ordered by descending token ID. Invalid packed indices remain `-1` instead of
being converted into a preceding-shard token.

Flags:

```text
LLAMA_DFLASH_TP_TOP_K=1
LLAMA_DFLASH_CANDIDATE_TOP_K=15
LLAMA_BACKEND_GREEDY_BATCH_ROWS=1
LLAMA_TP_BACKEND_SAMPLING=1
GGML_SYCL_COMM_TOP_K=1
```

The usual retained target/DFlash device-sampling, submission, cache, and RMS
fusion flags remain part of the run identity. Candidate counts above 32 fall
back to the CPU sampler rather than entering this experimental kernel.

## Correctness and smoke

The final 64-token proof after the kernel hardening produced:

| class | tok/s | drafted / accepted | response SHA prefix |
| --- | ---: | ---: | --- |
| prose | `66.033` | `155 / 48` | `f45a2f2c58f1ca34` |
| code | `108.685` | `126 / 53` | `2ca4135046a15a71` |
| JSON | `208.712` | `65 / 58` | `32dc3aebb11684a4` |

All hashes and proposal histories match the retained RMS-fusion 64-token
smoke. The log proves the intended one-row and batched 16-row communicator
paths. `llama-server` and `test-sampling` built successfully; the sampler unit
suite passed.

Evidence:

- final smoke identity:
  `sweeps/20260813-dflash-tp-topk-hardened-smoke.json`;
- final JSONL SHA256: `ba80405970802f5abbc437338e7a5393e3034cd68bf832b3f05ceda6914edea2`;
- final server-log SHA256: `9f10351b799f06c21ddaeb554596b93f26ed7b47c900e0b47e1cfacc0312cacb`;
- full device-top15 trace identity:
  `sweeps/20260813-dflash-ddtree-device-top15-trace.json`;
- trace JSONL SHA256: `5a6baac86ebf64fa8bbbded48b713b7a851fac5927eecbc20bd90fff9de53ceb`;
- trace server-log SHA256: `9d76cac744b386e3638e83863462aee3e68e3211fa48ddc1f5ee18bd894a94d4`;
- structured coverage analysis:
  `data/muse-ddtree-device-top15-coverage-20260813.json`.

Production was restored without reboot. Both services are active and the full
model, cache-zero code, and vision health gate passes in
`data/muse-health-20260813-dflash-tp-topk-final-smoke-restore.json`.

## Adjacent profile C/A/C

A subsequent canonical 256-token greedy/top15/greedy C/A/C used the same
binary, prompts, TP4 identity, and `LLAMA_SPEC_PROFILE=1`. All response hashes
were canonical and all accepted counts matched. Prose drafted count differed by
one (`1198 / 1199 / 1199`); code and JSON proposal histories matched exactly.

| arm | prose | code | JSON | mean tok/s |
| --- | ---: | ---: | ---: | ---: |
| greedy before | `56.317` | `81.343` | `99.169` | `78.943` |
| top15 | `54.422` | `78.644` | `96.014` | `76.360` |
| greedy after | `56.194` | `81.371` | `99.115` | `78.893` |

At 128 cumulative rounds, the direct DFlash profile reports
`6.25 / 8.06 / 6.26 ms` for greedy-before/top15/greedy-after. The matched
top15 cost is therefore approximately **`1.805 ms/round`**. This supersedes
the earlier non-adjacent `0.8--1.0 ms` estimate.

Evidence:

- identity: `sweeps/20260813-dflash-topk-adjacent-profile-cac.json`;
- JSONL:
  `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/dflash-topk-adjacent-profile-full-cac-20260813.jsonl`;
- JSONL SHA256: `874dbf3fd7fa448436fe7507a1502ad0cde0c5300eea512dc74372c9c9d9b7a7`;
- before/candidate/after server-log SHA256:
  `436af38b259dc239fc28f55c995c3333ba2c2859f471f625a7b743b6f936ef9f`,
  `722e5825299f4a3a1b59008cb0ed67e9faec2a08fd42f5956c99566665673821`,
  and `f63e1e02cffb23ea4351b495a13e8f778545f1d876de7cb8afe6878a140cb6a2`;
- restored production health:
  `data/muse-health-20260813-dflash-topk-adjacent-profile-full-restore.json`.

## Ceiling and next action

The full device-top15 prefix trace requires `66 / 48 / 42` target rounds for
prose/code/JSON. Using the measured top-k round costs gives
`70.897 / 97.517 / 113.909 tok/s`, arithmetic mean `94.108`.

The adjacent profile pins top-k at approximately `1.805 ms/round`. Removing
that entire cost would project the zero-bookkeeping DDTree ceiling to about
`97.34 tok/s`; another roughly `1.39 ms/round`, plus measured tree overhead,
would still be required.

The first local kernel target was the lane-zero serial merge of 128 sorted
15-candidate lists. The measured parallel replacement follows. Do not start
the full server/KV tree rewrite until the kernel work and unified-KV gate make
the arithmetic credible.

## Parallel local-list merge

Source commit `e5d4efaf9` replaces the lane-zero insertion merge with a
default-off seven-level pairwise merge tree under
`GGML_SYCL_TOP_K_TREE_MERGE=1`. The per-lane vocabulary scan is unchanged.
Each active lane merges two complete sorted lists into its existing private
arrays before writing the left shared-memory slot, so the kernel keeps the
same 15 KiB SLM footprint at k=15.

The canonical 256-token serial/tree/serial C/A/C produced canonical hashes and
matching accepted counts in every arm:

| arm | prose | code | JSON | mean tok/s |
| --- | ---: | ---: | ---: | ---: |
| serial before | `54.509` | `78.370` | `95.737` | `76.205` |
| tree merge | `54.701` | `79.083` | `96.360` | **`76.715`** |
| serial after | `54.530` | `78.698` | `95.846` | `76.358` |

Against the pooled controls, throughput improves approximately **`0.568%`**.
The direct 128-round DFlash profiles are `8.04 / 7.77 / 8.04 ms`, so the
kernel saves approximately **`0.27 ms/round`**. Prose drafted count differed by
one in the candidate (`1198` versus `1199`); code/JSON proposal counts and all
accepted counts matched.

Evidence:

- source commit: `e5d4efaf9`;
- identity: `sweeps/20260813-dflash-topk-tree-merge-smoke-cac.json`;
- JSONL SHA256: `ae4c269454093714d2bf64b0ef86067e2cdf8a8d72b198e1a2b9bca2222469c3`;
- serial-before/tree/serial-after log SHA256:
  `78ba9ed4cc12d6adcc49b126da213646ef54012c933f855cd82fe2c8088af099`,
  `ded79ae45f5818e5b230a569b649d62904b10fe045d62bd4c52fd504d4ac0eea`,
  and `80be9f2b3596f1bf3eb6a7f59bfccf72b7aed40c1438f48d810a0f58a49ba8a7`;
- production health:
  `data/muse-health-20260813-dflash-topk-tree-merge-full-restore.json`.

Retain this exact micro-win. The remaining top15-versus-greedy draft delta is
approximately `1.51 ms/round`, mostly in the per-lane vocabulary scan and
insertion plus the selected-value/collective/softmax tail. The next smallest
kernel screen is a guarded 256-lane k=15 variant to halve each lane's scan;
adjudicate SLM occupancy and full C/A/C timing before promotion.

## Wider k=15 scan

Source commit `aa64538b2` adds a default-off 256-lane specialization under
`GGML_SYCL_TOP_K_BLOCK_SIZE=256`; it is admitted only with tree merge enabled
and `k <= 16`. The 128-lane path remains the fallback. At k=15 the variant
uses 30 KiB SLM, doubles scan parallelism, and halves each lane's vocabulary
span.

The canonical 128/256/128 C/A/C kept canonical hashes and identical accepted
counts:

| arm | prose | code | JSON | mean tok/s |
| --- | ---: | ---: | ---: | ---: |
| block 128 before | `54.697` | `78.996` | `96.325` | `76.673` |
| block 256 | `54.896` | `79.509` | `96.801` | **`77.069`** |
| block 128 after | `54.580` | `79.117` | `96.141` | `76.613` |

Against pooled controls the gain is approximately **`0.554%`**. The direct
128-round DFlash profiles are `7.77 / 7.46 / 7.81 ms`, a pooled saving of
approximately **`0.33 ms/round`**. Retain it alongside the merge tree.

Evidence:

- source commit: `aa64538b2`;
- identity: `sweeps/20260813-dflash-topk-block256-smoke-cac.json`;
- JSONL SHA256: `676459811ac65f7e07a7706724098ff67d363b7a39922e0f83d1dc2d4ce00de5`;
- block128-before/block256/block128-after log SHA256:
  `f7c50088ac9e96fa23976e953840a11e5bee84e071ffb7b5e06dc00c583285d4`,
  `978a804772d5684375ea372500b90f9b7e4c81b2278b5ba6180fe52c01fbc97d`,
  and `3a169f6c54783eba05a249b0e478c8cfdc058e50d3cb45a9af7ad958ff7ec9c1`;
- production health:
  `data/muse-health-20260813-dflash-topk-block256-full-restore.json`.

Together the tree merge and wider scan recover approximately `0.60 ms` of the
original `1.805 ms` top15 cost. About `1.2 ms/round` remains between optimized
top15 and greedy, while the zero-bookkeeping DDTree route still needs roughly
`2.6 ms/round` total savings to average 100. The next work should isolate the
remaining local insertion versus selected-value/collective/softmax tail before
another kernel rewrite.

## 512-lane scan

Source commit `7fc0c977c` extends the guarded specialization to 512 lanes for
`k <= 16`. At k=15 it uses about 60 KiB SLM, near the useful limit, but the
canonical C/A/C shows that occupancy remains acceptable:

| arm | prose | code | JSON | mean tok/s |
| --- | ---: | ---: | ---: | ---: |
| block 128 before | `54.750` | `79.262` | `96.353` | `76.788` |
| block 512 | `55.229` | `79.844` | `97.364` | **`77.479`** |
| block 128 after | `54.806` | `79.068` | `96.421` | `76.765` |

The gain versus pooled controls is approximately **`0.915%`**. Direct
128-round DFlash profiles are `7.75 / 7.22 / 7.73 ms`, a pooled saving of
approximately **`0.52 ms/round`**. Hashes, proposal counts, and accepted counts
match exactly across all arms.

Evidence:

- source commit: `7fc0c977c`;
- identity: `sweeps/20260813-dflash-topk-block512-full-cac.json`;
- JSONL SHA256: `70b1a3565cfc021a11d6b911ce8615020d1b2070fa5bd543b2e1eb0e52512b59`;
- block128-before/block512/block128-after log SHA256:
  `93c51fa86ab93c280f59aa0b0ece87b0fbafde411ce04653cbc0e82d65e2f04d`,
  `ad4b5ff98d6c084a960af4828133d361c68285592816bab97870c3b0b3d0cd79`,
  and `fee814489e6d1665bc7a802b13c5f19a2968be57a32b8dc3fc6336be187002fb`;
- production health:
  `data/muse-health-20260813-dflash-topk-block512-full-restore.json`.

Use `GGML_SYCL_TOP_K_TREE_MERGE=1` plus
`GGML_SYCL_TOP_K_BLOCK_SIZE=512` for the current top15 kernel best. Relative
to the original serial 128-lane path, tree merge plus block512 recover roughly
`0.82 ms` of the `1.805 ms` top15 cost. Approximately `0.98 ms/round` remains
versus greedy, and the zero-bookkeeping DDTree route still needs about
`2.37 ms/round` more total savings to average 100. A 1024-lane version would
require about 120 KiB SLM and is rejected on this hardware; close this scaling
axis and isolate the fixed selected-value/collective/softmax tail next.
