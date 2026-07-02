# Gemma 4 26B Q8 Verifier Row-Adaptive Read-Only Audit

Date: 2026-07-02

## Purpose

After the record-stack node profile showed the target/verifier LM head as the
largest remaining short-decode hotspot, we re-audited whether an exact
row-adaptive verifier could be implemented as a small patch. This was a
read-only source audit. No files were edited for this lane.

## Current Row Semantics

With the promoted recipe (`n_max=3`, `n_min=2`), MTP drafts are normally
two or three tokens. Drafts shorter than `n_min` are cleared in
`common/speculative.cpp`.

The default full-bonus verifier batch is built in
`tools/server/server-context.cpp`:

| row | input token | target output used for |
| ---: | --- | --- |
| 0 | last sampled token `S` | verify `draft[0]` |
| 1 | `draft[0]` | verify `draft[1]` |
| 2 | `draft[1]` | verify `draft[2]`, or bonus if `n_draft=2` |
| 3 | `draft[2]` | bonus if `n_draft=3` |

On first mismatch, `common/sampling.cpp` returns prior accepted draft tokens
plus the true target top token for the failing row. On full match, it appends
the bonus row.

MTP hidden-state carry follows accepted draft count, not emitted-token count:
`common_speculative_accept(..., n_accepted)` copies `verify_h[n_accepted]`
after clamping and `verify_h_base` adjustment. For full `n_draft=3` plus
bonus, `accept(..., 3)` copies row 3 while the bonus becomes `slot.sampled`
for the next step.

## Why The Existing Simple Path Lost

The current exact accept-prefix backend is already the simple row-adaptive
implementation:

- `LLAMA_SPEC_VERIFY_ACCEPT_PREFIX_ARGMAX=1` routes Gemma verifier output to
  `ggml_mul_mat_argmax_accept_prefix()` in `src/models/gemma4.cpp`.
- The SYCL path loops `out_idx=0..nvec-1` in
  `ggml/src/ggml-sycl/mmvq.cpp`, launching/reducing each row conditionally.
- It avoids later LM-head rows after a mismatch, but it loses multi-row
  efficiency and pays serial per-row launch/reduction overhead.

The prior top1-epilogue follow-up preserved exactness but still carried that
row dependency. Recorded A/B: candidates averaged `105.080 tok/s` versus
controls at `116.498 tok/s`, a `-9.80%` regression.

Post-hoc accept-prefix masking and candidate-vs-max variants do not remove the
expensive full-vocab work. Conditional/no-bonus/late-head/prefix-tail variants
either lose the useful bonus pipeline or add extra decode/head boundaries.
The row-economics profile showed the bonus was useful in `541/921` steps, and
the oracle row-output saving ceiling was only `21.365%`.

## Decision

There is **no small credible exact row-adaptive verifier patch** left in the
current architecture.

The only credible future verifier lane is a new non-serial backend LM-head
path that keeps one target decode and current `n_draft+1` verifier rows, but
computes row 0, decides match on device, and computes row 1/2/bonus only if
needed without per-row host launches. That likely needs a new guarded GGML/SYCL
op or persistent/cooperative backend design and is high risk.

Main risks for any future implementation:

- exact argmax tie-breaking;
- suppress-token / output-scale cases;
- grammar / non-greedy exclusions;
- `n_draft=2` short-tail handling;
- sampled-row `-1` fallback bugs;
- SYCL global synchronization or conditional graph support.

Required validation for a future attempt:

1. Null-sensitive parity against the current full-bonus verifier path.
2. Canary and emitted-token hash parity for `n_draft=2` and `n_draft=3`.
3. Profiling proof that no extra decode call is introduced and target verifier
   LM-head time actually drops.
4. Strict128 and full512 fixed realistic A/B with GPU crossover,
   `cached_tokens=0`, unchanged UD-Q8_K_XL target/verifier and Q4_0 draft.

## Evidence Links

- `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-acceptprefix-top1-epilogue-negative.md`
- `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-candidate-bound-lmhead-proof-design.md`
- `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-row-economics-profile.md`
- `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-conditional-bonus-negative.md`
