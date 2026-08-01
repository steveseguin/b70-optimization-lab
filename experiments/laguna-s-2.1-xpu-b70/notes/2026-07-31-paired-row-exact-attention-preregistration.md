# Laguna paired-row exact M12 attention

Date: 2026-07-31 America/Toronto

Status: **preregistered before source change, build, or device execution.**

## New mechanism

The exact verifier currently launches one paged-decode workgroup per
`(verifier row, KV head)`.  On TP4, each row has 12 Q heads and 2 KV heads, so
each KV head owns only six real Q rows while the compiled qgroup-16 policy has
ten unused rows.

Pair two consecutive verifier rows and place both six-head GQA groups in one
qgroup-16 tile.  This reduces the exact verifier from 12 to 6 logical decode
batches and lets one K/V load feed both temporal rows.  For each pair, the
earlier row masks the final KV token and uses a sliding-window origin one token
earlier; the later row uses the pair's maximum staircase length.  The QK,
softmax, and PV tile shapes and per-row reduction order remain the incumbent
qgroup-16/page-64 policy.

The first component may explicitly pack Q and unpack O outside its timed core.
That isolates whether the kernel mechanism is exact and large enough before
any vLLM integration.  A later integrated screen must include those costs.

## Candidate

- Kernel base: `99886d783372e621941228250091dc8ebdc1595d`.
- Worktree: `/home/steve/src/laguna-xpu-kernels-paired-attn-20260731`.
- Selector: `VLLM_XPU_LAGUNA_M12_PAIR_ATTN`, literal `0` or `1`, default off.
- Candidate-only physical input: batch 6, 24 Q heads, 2 KV heads, head 128,
  BF16 Q/K/V, page 64, qgroup-16, consecutive staircase pairs.
- Selector-on must fail closed for every other shape, dtype, layout, sequence
  relation, mask, or page policy used by the component.
- Selector-off dispatch and device code remain the promoted path.

## Gates

1. Focused host tests must cover selector parsing, shape rejection, pairing
   and inverse layout, staircase lengths, and both full and sliding masks.
2. Build only the reduced Laguna attention library with pinned oneAPI 2025.3;
   record source commit, DSO SHA-256, `libsycl` SONAME, elapsed time, peak RSS,
   and swaps.
3. On one idle B70, compare the candidate after inverse layout with the
   incumbent 12-batch output for the 52 real-window contexts, full and
   sliding attention, and at least two changing seeds.  Require raw BF16
   equality in every case.
4. Time the attention core with fixed prepacked inputs and caller-owned
   outputs.  Require at least 1.5 ms projected saving across 12 full plus 36
   sliding layers before paying for vLLM integration; this leaves margin for
   pack/unpack work while the 130-tok/s gap is about 1.13 ms/cycle.
5. A component pass authorizes only default-off vLLM integration and an
   all-cost component screen.  Smoke and endpoint gates require a new frozen
   authorization with the unchanged 13/13 teacher, cache-zero, one start,
   146/145 target and 14/13 draft topology, and clean idle.

No weight, target or draft precision, BF16 KV semantic, verifier width, draft
depth, target verification, sampler, acceptance rule, prompt, output length,
or score metric may change.  No reset, driver reload, FLR, reboot, or
privileged recovery is authorized.
