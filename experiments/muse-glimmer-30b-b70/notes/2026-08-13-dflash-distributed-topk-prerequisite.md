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

## Ceiling and next action

The full device-top15 prefix trace requires `66 / 48 / 42` target rounds for
prose/code/JSON. Using the measured top-k round costs gives
`70.897 / 97.517 / 113.909 tok/s`, arithmetic mean `94.108`.

The observed top-k cost is roughly `0.8--1.0 ms` per draft call. Even deleting
all of it leaves more than two milliseconds per round to find, before tree
bookkeeping. Therefore do not start the full server/KV tree rewrite as the
primary campaign yet.

Next, run an adjacent profile-enabled top15-versus-greedy timing A/B to pin the
top-k cost, then a zero-code unified-KV linear parity/timing gate. Continue the
primary campaign on independent target/verifier kernel savings; integrate the
tree only after roughly `2.5--3 ms/round` more exact savings are demonstrated.
