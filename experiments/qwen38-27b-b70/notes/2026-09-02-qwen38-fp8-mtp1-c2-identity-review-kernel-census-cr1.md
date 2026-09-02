# Qwen3.8 FP8 TP2 MTP1 c1/c2 identity: review of R64-R116 and kernel census (CR1)

Date: 2026-09-02. Independent review of the R64-R116 localization series plus a
direct operator census run on one B70 inside the frozen R116 image
(`sha256:91e591590f96247cd318bb229e7909ea1c036be201e62b646679e1ea02eab08f`).
Classification: review plus operator diagnostic. No speed, quality, README,
website, or LocalMaxxing claim follows from anything here.

## Summary

1. The c1-versus-c2 "bug" is an exact float16 logit tie. R67's logprob
   diagnostic recorded the sequential top two at `cache-c000` index 96 as
   `-1.234007477760315` for both ` *` (348) and ` **` (2972). Greedy argmax
   breaks the tie by index in c1; any one-ULP change anywhere in the 64-layer
   forward pass decides it the other way. The record already contains eight
   independent c1 flips to the same alternate stream from ULP-level changes
   that touched no request packing at all: R87 (qkvz padded to 256), R91, R92,
   R94, R96, R97, R98 (norm kernel variants) and R110 (trace ops that moved
   Inductor fusion boundaries).
2. R115's `38/38` and R116's `2/2` packed passes were not bitwise identity.
   Re-analysis of R115's own trace
   ([`r115-trace-reanalysis`](../data/2026-09-02-qwen38-fp8-mtp1-r115-trace-reanalysis-cr1.json))
   shows the cache request's post-norm and `out_proj` digests differ from the c1
   control at **48/48 GDN layers on both ranks, including layer 0**, and differ
   between the `[31,28]` and `[28,31]` orders at 46/48 layers. Every shape is
   internally deterministic (one digest per order). The passes were the tie
   landing on 348 under two particular perturbation histories.
3. The census names the non-invariant operators directly. The oneDNN
   `fp8_gemm_w8a16` kernel used by every FP8 linear returns different per-row
   bits in M-classes roughly `{1-4}`, `{5-8}`, `{12-48}`, `{59-64}`, `{96}`,
   `{128}`, `{256}`, `{512}`; it is position-dependent at M>=59 for the
   K=3072/K=8704 shapes; and it is **run-to-run nondeterministic for M in about
   168-256** on four of the six production shapes. Everything else tested is
   row-invariant: both GDN gated-norm arms, eager and standalone-Inductor
   `RMSNormGated`, the 5120-wide RMSNorm, the FP16 `lm_head` matmul, the GDN
   core (R84), and the paged-attention decode split plan below 2,048 tokens.
4. The R101 selector's R97 multi-request arm is a deliberate ULP perturbation
   with no invariance benefit: R99 alone is row-invariant across every M
   tested, and R97 differs from R99 in 6 of 1,416 rows by one ULP. R97's
   "c2-exact" reputation came from single-trial c2 results that R105 later
   showed were prefill-order draws.
5. The staggered failure needs no new mechanism. In the mixed step, request A's
   two decode rows share every packed GEMM with request B's 28 prefill rows
   (M=30, class `{12-48}`) instead of running at M=2 (class `{1-4}`) as in c1.
   R116 isolated only the layer-0 MLP; the other roughly 380 GEMM calls in that
   step perturb A's residual and cache state, and the tie flips 54 steps later.
6. Consequence: layer-N-only request isolation cannot converge on identity.
   Identity at any concurrency requires a row-invariant GEMM for every M this
   lane can schedule, plus removal of the R97 arm, plus a regenerated c1 oracle.

## Kernel census

Harness: [`qwen38-fp8-kernel-batch-invariance-census.py`](../scripts/qwen38-fp8-kernel-batch-invariance-census.py),
[`...-census-followup.py`](../scripts/qwen38-fp8-kernel-batch-invariance-census-followup.py),
[`qwen38-fp8-kernel-determinism-sweep.py`](../scripts/qwen38-fp8-kernel-determinism-sweep.py).
Random data at the real per-rank TP2 shapes, seed 20260902, one B70
(`ONEAPI_DEVICE_SELECTOR=level_zero:1`), image entrypoint overridden to
`python3` with `--workdir /tmp` so the patched site-packages vLLM is imported.
Results: [`census result`](../data/2026-09-02-qwen38-fp8-kernel-batch-invariance-census-cr1-result.json),
[`follow-up`](../data/2026-09-02-qwen38-fp8-kernel-batch-invariance-census-cr1-followup.json),
[`determinism sweep`](../data/2026-09-02-qwen38-fp8-kernel-determinism-sweep-cr1-result.json),
[`artifact hashes`](../data/2026-09-02-qwen38-fp8-kernel-batch-invariance-census-cr1-artifact-sha256.txt).
Host run directory `/mnt/fast-ai/bench-results/qwen38-fp8-kernel-invariance-census-20260902-cr1`.
Both B70s reported `normal` afterwards; the only kernel line in the window was
`xe 0000:03:00.0: [drm] Xe device coredump has been deleted` (cleanup of the
earlier R116 attempt-1 reset, not a new event).

### `fp8_gemm_w8a16` row-0 value classes by M (bitwise)

| Per-rank shape (K→N) | Classes of M sharing one row-0 result |
| --- | --- |
| gdn_in_proj_qkvz 5120→8192 | {1-4} {5-8} {12-32} {48-512} |
| gdn_out_proj 3072→5120 | {1-4} {5-8} {12-48} {59-64} {96-128} {256} {512} |
| attn_qkv_proj 5120→7168 | {1-4} {5-8} {12-32} {48,96,128} {59-64} {256} {512} |
| attn_o_proj 3072→5120 | {1-4} {5-8} {12-48} {59-64} {96} {128} {256} {512} |
| mlp_gate_up_proj 5120→17408 | {1-4} {5-8} {12-48} {59-128} {256} {512} |
| mlp_down_proj 8704→5120 | {1-4} {5-8} {12-48} {59-64} {96} {128} {256} {512} |

Differences between classes are one to two float16 ULPs (`6e-5` to `2.4e-4`).
Reading for this lane: c1 decode (M=2) and c2 decode (M=4) share a class, which
is why R85 saw identical layer-0 projections; c3 and above (M>=6) do not, which
is why R63 lost identity at every concurrency from c2 upward once prefill and
mixed steps are included. Prefill of 31 rows (class `{12-48}`) and packed 59
rows (class `{59-64}`) differ, which is the R86/R115 layer-0 observation.

### Position dependence, padding, determinism

- Permuting rows permutes the output bitwise for every shape at M<=48
  (16, 24, 32, 40, 48 tested with three permutations each). At M=59/64/128 the
  K=3072 and K=8704 shapes (`gdn_out_proj`, `attn_o_proj`, `mlp_down_proj`) are
  position-dependent; `attn_qkv_proj` is position-dependent at 59, 64 and 256.
  This is the R105 order effect: the same 31 rows at offset 0 versus offset 28
  inside a 59-row call.
- Real rows of a padded call do not depend on pad contents where the kernel is
  deterministic; padding to 32 reproduces the natural M=31 result, larger
  buckets do not (different class).
- Repeat determinism holds for all M<=160 and for 257-512, but **`gdn_out_proj`,
  `attn_qkv_proj`, `attn_o_proj` and `mlp_down_proj` return different bits on
  identical inputs for M in 168-256** (13-14 of the swept points each; max
  difference `1.2e-4`). `gdn_in_proj_qkvz` and `mlp_gate_up_proj` were
  deterministic at every swept M. M above 512 was not swept.

### Other operators

- GDN gated RMSNorm: R99 arm, R97 arm, eager `RMSNormGated.forward_static` and a
  standalone `torch.compile` of it are each row-invariant across M in
  {1,2,4,8,31,59,64,128,512} and repeat-deterministic. R99 and R97 differ from
  each other (6/1,416 rows, `1.2e-4`) and both differ from eager (`4.9e-4`).
- 5120-wide RMSNorm: eager and standalone Inductor both row-invariant.
- FP16 `lm_head` (`lm_head.weight` carries no FP8 scale in this checkpoint, so the
  W8A16 lm_head row in the census is not the production head): deterministic
  at every M; classes {1-32} {33-128} {136-320} {328-512}.
- Paged-attention decode split plan (`build_decode_split_plan`, kv tile 64,
  inferred 20 Xe cores, 2 local KV heads): one split for any sequence under
  2,048 tokens, so invariant for the 256-token fixture. At 2K-32K a lone
  sequence gets 8-22 splits while the same sequence in a c64 batch gets 1, so
  deep-context identity would also need a fixed split policy. The installed
  vLLM `_xpu_ops` never passes `num_splits_kv`, so the current stack appears to
  run single-split always; confirm before relying on it.

### Screening latencies (single GPU, random data, not a claim)

The W8A16 decode plateau is flat: `mlp_gate_up_proj` 166-170 us for M=1..16,
173 at 32, 200 at 64, 275 at 128; `mlp_down_proj` 78-84 us to M=16, 100 at 32;
`gdn_in_proj_qkvz` 73-77 us to M=32. Padding decode GEMMs to 32 rows therefore
costs almost nothing. `attn_qkv_proj` is the outlier: 172-183 us at M<=16 but
66 us at M=32 and 79 us at M=128, so oneDNN's small-M kernel choice for this
shape is about 2.7x slower than its M=32 kernel (16 attention layers, roughly
1.8 ms per decode step if it reproduces in situ).

## What this changes

- **Diagnosis.** Codex's handoff hypothesis ("a batch-shape or request-order
  dependent numerical transition in the layer-0 mixed prefill/decode path") is
  right that the cause is batch-shape-dependent rounding and right that mixed
  steps expose it, but wrong that it is a layer-0 defect or a state bug. It is
  the whole-model GEMM kernel, detected through one exact tie. Hypotheses 1-4 in
  the handoff (GDN state, spec reordering, selector misclassification, residual
  handoff) are not supported; R82/R83/R84 and this census clear them.
- **Method.** Token-stream bisection on the two-prompt fixture is closed. It has
  one coin; a 40/40 pass means the coin landed the same way 20 times under one
  schedule, not that the arithmetic is invariant. Use the census as the operator
  gate for any candidate: all M in one class, permutation-invariant at every M,
  repeat-deterministic, then regenerate the c1 oracle from the candidate build
  and run the c1-c64 identity ladder.
- **Publication.** Nothing is blocked. The FP8 package already publishes its
  MTP1 and MTP0 aggregate curves as output-audited with "greedy output is
  batch-shape-dependent". Identity qualification is an upgrade, and the honest
  label stands until a row-invariant build passes the ladder.
- **New risk.** The 168-256-row nondeterminism means a single request whose
  prefill (or chunk) lands in that range is not repeatable even at c1. The strict
  suite prompts are 48-78 tokens and the depth suites are 2K+ so past gates did
  not sample it, but any public determinism statement should carry this bound
  until an end-to-end c1 repeat with a ~200-token prompt is run.

## Recommended order of work

1. Drop the R97 arm (force the R99 path for every phase). Zero cost, removes a
   known deliberate perturbation, and keeps c1 bit-identical to the frozen
   oracle because c1 already runs R99. It is not a fix by itself.
2. Cheapest invariance experiment: build `fp8_gemm_w8a16` with a runtime M
   dimension (`DNNL_RUNTIME_DIM_VAL`) in the kernel worktree so oneDNN cannot
   specialize by M, then rerun the census. Adopt only if every class collapses,
   permutation invariance holds at all M, and the 168-256 nondeterminism is
   gone; measure the decode plateau cost.
3. If oneDNN cannot be made invariant, write a row-invariant Triton W8A16 GEMM
   (fixed BLOCK_K reduction order, FP32 accumulation, in-kernel block-scale
   dequant) for the six shapes; gate it with the census, then the identity
   ladder. Alternative with no new kernel: run every decode GEMM in fixed 32-row
   chunks and every prefill request alone at a power-of-two bucket; invariant by
   construction from these results, but roughly 2.5x GEMM time at c64.
4. Regenerate the c1 oracle from the invariant build; the frozen R72 oracle is a
   localization tool, not a requirement.
5. Harden the identity fixture: mine tokens whose top-two float16 logits tie or
   sit within one ULP across many prompts so the gate has more than one coin.
6. Report the 168-256 nondeterminism upstream (vllm-xpu-kernels / oneDNN) and add
   an end-to-end c1 repeat at that prompt length to the strict protocol.
7. Schedule the clean reboot that R62 and every speed claim since 2026-09-01
   have been waiting for.

## Reporting boundary

Operator diagnostic and review only. Census timings are single-GPU,
random-data screening numbers with no TP collective and must not be quoted as
lane performance. No README, website, package, or LocalMaxxing change.
