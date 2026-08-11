# Campaign: 100 tok/s Lossless BF16 Decode (opened 2026-08-11)

Operator goal: 100 tok/s decode on Muse Glimmer 30B BF16 without quality
degradation, horizon one to two weeks. Baseline at open: 42.7 json / 37.7
code / 24.3 prose per replica (2xB70, BF16 target, BF16 DFlash drafter
n15 p0.2), no-spec 9.85.

## Quality bar (unchanged, preregistered)

- BF16 target weights only; every emitted token is the target's greedy
  argmax under exact verification. Drafter-side changes (quant, fine-tune,
  trees) are quality-free by construction and always allowed.
- Kernel/topology changes (row split, batched-verify work) must pass:
  greedy task-suite parity vs the no-spec BF16 identity, long-context
  retrieval canaries, and repeat-stability characterization. Near-tie
  argmax flips under valid float orderings are accepted and documented;
  anything beyond near-tie divergence is a FAIL.
- No prompt/KV/response/history reuse in any measurement. Cold suite,
  `cache_prompt=false`, fixed prompts.

## Decode-time model (measured 2026-08-10/11)

- no-spec step: ~101.5 ms (55.7 GB weight read, 2-card sequential layer
  split; ~550 GB/s effective per card during its phase).
- spec round: drafter block pass (~10-15 ms BF16) + batch-16 verify
  (~110 ms) emitting E tokens. Today E ~= 5.3 (json).
- tok/s ~= E / round_time. Ceiling at E=16, current round: ~127.

## Lanes, ranked by expected multiplier

1. **L1 row-split fix (source, critical path).** `-sm row` segfaults at
   load for every quant incl. BF16. Fixing it halves the step ->
   verify ~55-60 ms -> 42.7 becomes ~75-80 at unchanged acceptance.
   First step: capture load backtrace, identify failing op, patch in a
   dedicated worktree with source snapshots.
2. **L2 cross-card drafter (source).** Mirror shared tensors
   (`output.weight`, embeddings) to the draft device so the drafter runs
   on the idle card and its cost leaves the round. +15-20%. Also restores
   mmproj coexistence with the BF16 drafter.
3. **L3 acceptance uplift (drafter-side, quality-free).**
   a) draft-tree / multi-branch verification (verify 2-3 candidate
   branches in one batch; needs upstream spec-path extension);
   b) drafter fine-tune (LoRA) on target outputs sampled from our serving
   distribution - self-distillation, exact verification unchanged;
   c) drafter head cost reduction (202K-vocab head is ~half the drafter).
   Prose (E ~= 2.9) is the class this lane must move.
4. **L4 verify-overhead shaving.** Profile batch-16 vs single step;
   close the ~8-15% gap (graph launch, small-batch matmul tails,
   softcap/argmax epilogue fusion opportunities).

Multiplication to target: L1 (x1.8) x L2 (x1.15) x L3 (+20-30% E) reaches
95-110 on json/code; prose additionally needs L3 to roughly double its E.

## Rules of the road

- Patched trees go under `/home/steve/src/` per-lane with cumulative
  source snapshots in `patches/muse-glimmer-30b-b70/source-snapshots/`.
  The clean-master production build stays untouched for serving.
- Production fleet keeps running between experiments; GPU pairs are
  borrowed for measured windows and returned. After any fleet config
  change: per-card residency check + decode canary (host-fallback rule).
- Every sweep lands in `sweeps/` with quality status. Records only after
  the full cold gate; no LocalMaxxing submission from the spec path until
  its determinism story is settled.

## Log

- 2026-08-11: campaign opened at 42.7/37.7/24.3.
- 2026-08-11 00:40: L1 first evidence: `-sm row` SIGSEGV is inside
  `ggml_backend_sycl_split_buffer_type()` during `load_tensors`
  (backtrace: `diagnostic-suites/20260811-smrow-segv-backtrace.log`).
  `-fit off` does NOT avoid it - the split-buffer implementation itself
  crashes, both via the fit probe and the real load. Next: read the
  function, find the deref, patch in a dedicated worktree.
- 2026-08-11 01:10: L1 pivot - upstream `-sm tensor` (meta-backend TP with
  SYCL N=2 ring allreduce) WORKS for Muse Glimmer on clean master, superseding
  legacy row split (whose ABI/rounding/selection bugs are patched and
  snapshotted in the muse-100 worktree, but the lane is parked). TP2 measured:
  no-spec 15.29 (1.55x layer), dflash n15 p0.15 = 56.2 json / 49.1 code /
  31.9 prose. Production text lane upgraded to TP2: 53.6 tok/s live (64K ctx).
  N=4 TP blocked by gated-attention elementwise MUL shard mismatch
  (`attn_out` x `attn_gate_sig`, both axis-0, different boundaries; aligns at
  N=2 by coincidence). Fix design: anchor attn_gate.weight split config to the
  attention rotation anchor. This is the remaining critical path to 100.
- 2026-08-11 01:45: N=4 TP UNBLOCKED functionally: the gated-attention MUL
  mismatch was a missing granularity case - `attn_gate.weight` fell through
  to granularity 1 while Q/out use `granularity_q` (KV-group packing).
  Three-line fix in `llama_meta_device_get_split_state` granularity rules
  (snapshot: `20260811-muse100-n4-gate-granularity.patch`). N=4 output
  correct. BUT N=4 performance is flat vs N=2 (no-spec 15.4 vs 15.3;
  dflash 45.4 vs 56.2 json): `ggml_backend_sycl_comm_init` implements the
  fast ring allreduce for N=2 only; N=4 falls back to the generic meta
  path. Remaining critical path to 100: extend the SYCL allreduce to N=4
  (projected no-spec ~28-30, dflash json ~75-90), then acceptance/verify
  polish for the last stretch. Production remains 2xTP2: text 53.6 live.
