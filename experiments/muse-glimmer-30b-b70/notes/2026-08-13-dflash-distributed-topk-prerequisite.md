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

The local SYCL top-k kernel currently makes lane zero serially merge 128 sorted
lists of 15 candidates. Replace that `O(128*k^2)` lane-zero phase with a
tie-stable parallel merge tree and measure it against this C/A/C. Then run a
zero-code unified-KV linear parity/timing gate. Do not start the full server/KV
tree rewrite until the kernel work and unified-KV gate make the arithmetic
credible.
