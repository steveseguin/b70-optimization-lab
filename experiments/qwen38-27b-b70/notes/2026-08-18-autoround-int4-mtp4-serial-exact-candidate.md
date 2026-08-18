# Qwen3.8 AutoRound MTP4 serial-exact GDN candidate

Date: 2026-08-18

Status: source-verified, not built or run

## Motivation

The first Qwen3.8 AutoRound TP2/MTP3 A/B pair is self-deterministic on all 25
prompts. It reports about `64.8%` average draft acceptance with typical
per-position acceptance near `0.84`, `0.65`, and `0.48`. A fourth draft
position is therefore worth measuring, but the older MTP4 diagnostic had to
disable the serial-exact GDN proof path. It measured `93.680 tok/s`, reproduced
only 9/25 prompts, and is not promotable.

## Source finding

At XPU-kernels commit
`2dd55f380df753a10a88fcd9e96192561066e713`, the serial-exact implementation is
already shape-driven except for two literals in
`csrc/xpu/gdn_attn/gdn_attn_interface.cpp`:

- the entry guard requires exactly four verifier rows; and
- the recurrent loop executes exactly four positions.

The persistent scratch cache keys on and allocates `total_spec_tokens`.
`exact_core`, Q/K/V/B/A views, state columns, convolution publication, and
scatter sizes are already derived from the runtime row count. The candidate
therefore changes only the guard and loop bound. It intentionally accepts only
four or five verifier rows: the current MTP3 control and the proposed MTP4 arm.
Other shapes still fail closed.

Patch:
[`../patches/vllm-xpu-kernels-qwen38-mtp4-serial-exact-candidate-20260818.patch`](../patches/vllm-xpu-kernels-qwen38-mtp4-serial-exact-candidate-20260818.patch)
(`SHA256 2889a74a469e97a70189c90752c0ca13ae84801eaf690f2ba2caa20ba8fd916f`).

## Required experiment

Apply the patch to exact XPU-kernels base `2dd55f380d`, rebuild the same staged
runtime, and run a same-binary pair:

1. MTP3 control: the accepted deterministic configuration, four verifier rows,
   capture size 4.
2. MTP4 candidate: `VALIDATION_NUM_SPECULATIVE_TOKENS=4`, five verifier rows,
   capture size 5, while keeping
   `VALIDATION_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=1`.

Do not reuse the historical MTP4 result because it disabled serial-exact mode.
The candidate must retain every other deterministic flag and arithmetic policy.

Promotion requires:

- a new Qwen3.8 target-only quality oracle first;
- 25/25 complete-output equality against that oracle under target verification;
- A/B self-determinism, cache-zero, cold unique prompts, and complete raw rows;
- selection-12 reported beside all-25;
- no Xe fault/reset and the measuring host's memory envelope retained; and
- a repeatable improvement, not a favorable-prompt or aggregate-throughput row.

This patch makes no speed or quality claim. Position-four acceptance was only
`0.333` in the old non-reproducing MTP4 diagnostic, so MTP4 may still be neutral
or negative after correctness is restored.
