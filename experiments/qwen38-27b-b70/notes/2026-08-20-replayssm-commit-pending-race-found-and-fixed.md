# Second runtime race found and fixed: gdn_replayssm_commit_pending

2026-08-20, same-day follow-up to
`2026-08-20-autoround-int4-runtime-nondeterminism-found-and-pad-fix.md`.

## Finding

`gdn_replayssm_commit_pending` (the C++ kernel that folds accepted
speculation tokens into each request's conv state) had **two independent
data races** in
`vllm-xpu-kernels/csrc/xpu/gdn_attn/spec_decode.hpp`:

1. **In-place parallel shift race.** Work items were parallelized over
   `row × conv_dim × conv_base_len` elements; the item for `state_pos = i`
   reads `conv_state[i + accepted]` while the item for
   `state_pos = i + accepted` concurrently **writes** that same address.
   Any commit with `accepted > 0` was racy.
2. **Bookkeeping read/write race.** Every work item in a row reads
   `pending[slot]` (via `active_for_row`) while the row's `elem == 0` item
   writes `pending[slot] = 0` at the end. If the cursor item retired first,
   sibling items observed `pending == 0` and skipped their part of the
   shift — a partial, corrupted conv-state update.

Observed on GPU 0 with production-shaped tensors (64 slots, conv_dim 512,
conv_base_len 3, spec cache 32, max_spec 6, unique valid state indices):
**1 mismatching call per ~1000–4000 calls**, one slot partially updated
(223/1536 elements), values off by full magnitude (max_abs 3.55) — not
epsilon noise. Frequency in a 25-prompt strict run at MTP5: commits run per
GDN layer per accepted step ⇒ tens of thousands of calls per run, so
multiple corruptions per run are expected. A corrupted conv state persists
in the slot and compounds for the rest of that request.

This is a decode-time, spec-decode-specific race — exactly the class needed
to explain the margin-free 21/25 arm divergence on prompts whose prefill
never touches the int4 dirty band.

## Fix (patch: `../patches/vllm-xpu-kernels-qwen38-replayssm-commit-race-fix-20260820.patch`)

- Shift kernel: one work item per `(row, conv_elem)` column performs the
  shift-left-by-`accepted` **serially in ascending `state_pos` order**
  within the item (reads at `i + accepted` always precede the write at
  `i`; `i + accepted > i` is never written first). Race-free in-place
  shift, still fully parallel across rows × conv_dim.
- Cursor/bookkeeping update moved into a **second kernel**
  (`gdn_replayssm_commit_cursor_kernel`) submitted after the shift on the
  same queue. Queue ordering guarantees all shift-phase reads of
  `pending[]` complete before any cursor writes.
- Semantics preserved exactly (accepted clamping, flush/base/write_pos
  arithmetic, `pending[slot] = 0` on commit).

## Validation (staged build `/home/steve/staged-xpu-commitfix-20260820`)

Triple-fix build = GDN scratch zero-init + oneDNN int4 determinism pad +
this race fix.

| Gate | Result |
| --- | --- |
| commit_pending race sweep, fixed build | **0/4000** (was 1/4000, 1/1000) |
| reset_slots / copy_slots sweeps | 0/200 each (were already clean) |
| commit_pending vs torch reference (`_xpu_gdn_replayssm_commit_pending` fallback), 60 randomized trials over all 7 outputs | **60/60 bitwise equal** |
| int4 M-sweep with det-pad engaged | 0 mismatches at M=6..1024; pad engages for in-band M |
| GDN spec-op scratch bench | intact; persistent 59.0 µs vs ephemeral 71.1 µs, history-independent |

Evidence:
`../data/2026-08-20-replayssm-ops-determinism.json`,
`../data/2026-08-20-commit-pending-equivalence.json`
Manifest: `repro/qwen38-27b-autoround-int4-b70/manifests/staged-xpu-commitfix-20260820.sha256`
(`_xpu_C.abi3.so` 4dd33601..., `libgdn_attn_kernels_xe_2.so` unchanged
c194e28d...).

Harness scripts: `../scripts/qwen38-det-*.py` (replayssm sweep = the
combined determinism + equivalence harness in the same file family).

## Interaction with the divergence picture

- int4 prefill band (fixed separately) explains at most
  holdout--structured-extraction (187 tokens, in the [129,448] band).
- This race fires at decode time whenever MTP commits accepted tokens —
  independent of prompt length. It is the first measured mechanism that can
  flip factual-protocol (49), sql-debugging (71), and long-rollover (837).
- Whether it accounts for the *stable* per-prompt divergence pattern
  (same prompts diverge every pairing) is unproven: a ~1/4000 random race
  would scatter divergences. The observed stability may reflect the
  divergence *seeding early* in long generations and locking in, or
  additional data dependence. A margin-free A/B on this triple-fix build
  decides.
- Remaining unswept surface: GDN chunk prefill (Triton; standalone compile
  fails on this host — sweep server-side), cross-request history
  dependence.

## Recommended next run (measuring host)

Margin-free + PERSISTENT_SCRATCH=1 + this build (or equivalent patched
runtime), pinned shared compile cache, two arms, 25-prompt suite,
token-ID parity target 25/25. If clean, rerun with fresh compile caches to
re-test compilation determinism on top.
