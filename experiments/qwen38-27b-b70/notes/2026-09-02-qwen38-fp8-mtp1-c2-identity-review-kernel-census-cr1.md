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
`gdn_in_proj_qkvz` 73-77 us to M=32. The census also showed `attn_qkv_proj` at
172-183 us for M<=16 versus 66 us at M=32. **That reading was an artifact of the
census timing (one warmup call, ten iterations):** with ten warmups the same
kernel measures 64.8 us at M=2 (see the R118 section and
[`pad-overhead microbench`](../data/2026-09-02-qwen38-fp8-w8a16-pad-overhead-microbench-cr1.json)).
oneDNN does lazy first-call work on that shape; there is no slow steady-state
small-M kernel, and the census script now warms up ten times before timing.
Padding decode GEMMs to 32 rows is not free either: the K=3072 shapes roughly
double per call (13 to 24-27 us) and the others gain 4-12 us.

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

## Follow-up experiments run after the review

### R117: R99 gated-norm lowering for every phase

Image `neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-gdn-r99-all-phases-r117`
(`sha256:52fe73b0...66eedf`), R116 plus one change: the selector calls the impl
with `multi_request=False` for every live request count, so the R97 arm is
unreachable. Runtime flags unchanged. Preregistration and result:
[`r117-prereg`](../data/2026-09-02-qwen38-fp8-mtp1-gdn-r99-all-phases-r117-prereg.json),
[`r117-result`](../data/2026-09-02-qwen38-fp8-mtp1-gdn-r99-all-phases-r117-result.json),
[`phase summary`](../data/2026-09-02-qwen38-fp8-mtp1-gdn-r99-all-phases-r117-phase-summary.json).

| Phase | Exact |
| --- | --- |
| warm c1 | 1/1 |
| warm c2 (simultaneous) | 0/2 batches, 2/4 outputs |
| staggered c2 (200 ms launch stagger) | 0/4 batches, 4/8 outputs |
| counted c1 | 3/3 |
| counted c2 (simultaneous) | 0/10 batches, 10/20 outputs |

Every miss is `cache-c000` at zero-based index 96, `348` to `2972`, the same
alternate stream (`964a2e99...`). The layer-0 trace shows both packed orders
(five `[28,31]`, five `[31,28]`) and six staggered single-request entries; all
failed. Under R116 the same packed orders passed 38/38 and 2/2. The only
difference is the one-ULP R97 norm arm in multi-request phases, so that arm was
a compensating perturbation that happened to land the tie on 348, not a repair.
R117 is the cleaner base (no deliberate c1/c2 arithmetic split) and is not a
regression in any meaningful sense: neither build is bit-identical to c1 in any
packed GEMM. Both B70s normal afterwards, no kernel event.

### Endpoint probe: the 168-256-row nondeterminism is visible to users

Same R117 image, second server with `MAX_MODEL_LEN=1024`, everything else
unchanged. [`probe-qwen38-fp8-c1-prefill-length-determinism.py`](../scripts/probe-qwen38-fp8-c1-prefill-length-determinism.py)
built prompts whose `usage.prompt_tokens` hit 100, 168, 200, 224, 250 and 300,
then sent each identical request five times in sequence at temperature 0 with
`logprobs=5`, 64 output tokens, `cached_tokens=0` on every response. Result:
[`probe result`](../data/2026-09-02-qwen38-fp8-mtp1-r117-prefill-length-determinism-probe-result.json).

| Prompt tokens | Token IDs identical (5 repeats) | Logprob arrays identical |
| --- | --- | --- |
| 100 | yes | yes (1 distinct) |
| 168 | yes | **no (5 distinct)** |
| 200 | yes | **no (5 distinct)** |
| 224 | yes | **no (5 distinct)** |
| 250 | yes | **no (5 distinct)** |
| 300 | yes | yes (1 distinct) |

The differences are not one ULP at the output. At 200 tokens the first token's
logprob was `-0.1528`, `-0.1981` and `-0.1869` on three repeats; at 224 it was
`-0.6008`, `-0.6045` and `-0.6001`. Sixty-four layers amplify the GEMM's
`1e-4` row differences into few-percent probability shifts. Token IDs held for
these 64-token completions only because no near-tie was crossed; a longer
completion or a sampled request would not be repeatable. This matches the
kernel sweep window exactly and is a single-request determinism hole in the
lane for any prefill step of roughly 168-256 rows, which includes packed
multi-request prefills at c6-c8 with 30-token prompts, not just long prompts.
The strict 12-prompt suite (48-78 tokens) never enters the window, which is why
R53/R54 passed. Both B70s normal afterwards, no kernel event.

Implications: (a) public determinism language for this lane should state the
row-count bound until the kernel is fixed; (b) the identity ladder at c6-c8 is
confounded by this independent of the tie mechanism; (c) the upstream report to
vllm-xpu-kernels/oneDNN should cite the sweep's per-shape M lists and this
endpoint reproduction.

### R118 / R118b: fixed 32-row padding of small-M W8A16 GEMMs (closed)

R118 (`sha256:95742ce8...`) wraps every W8A16 linear in an opaque op that pads
calls below `VLLM_XPU_W8A16_DECODE_PAD_ROWS` rows up to the bucket and slices
the result, with execution markers; the repro launcher now forwards that
variable (the first attempt ran unpadded because it did not, and is kept as
`control2`). Result:
[`r118-result`](../data/2026-09-02-qwen38-fp8-mtp1-w8a16-decode-pad-rows-r118-result.json),
[`replicates`](../data/2026-09-02-qwen38-fp8-mtp1-w8a16-decode-pad-rows-r118-replicates.json).

| Arm (run order) | c1 wall tok/s | c1 after-TTFT tok/s | c2 wall tok/s |
| --- | ---: | ---: | ---: |
| control (pad 0) | 39.30 | 40.47 | 75.30 |
| control2 (pad 0) | 40.40 | 41.65 | 77.80 |
| candidate (pad 32, all shapes) | 35.78 | 36.81 | 69.02 |
| control3 (pad 0) | 36.78 | 37.86 | 69.46 |

The candidate sits below every control, but the controls drift 10% across the
session, so the boot cannot resolve the magnitude. The mechanism is settled by
the micro-benchmark instead: padding the K=3072 shapes to 32 rows doubles their
per-call cost, and the other shapes gain 4-12 us each, about 2-3 ms per decode
step in total; the attention-qkv small-M penalty that motivated the lead was a
warmup artifact of the census timing. R118b (`sha256:a9d12543...`, qkv-only
padding with a preallocated buffer) was built and preregistered but not run:
with no real qkv penalty there is nothing for it to recover. Both are closed.
Token streams were identical across all four arms.

The second padded replicate never reached readiness. While staging weights,
the second B70 (`0000:e3:00.0`) logged repeated copy-engine page faults with
`-EINVAL` responses, engine memory CAT errors, one `bcs` engine reset, a
timed-out job and a device coredump; the container was stopped gracefully,
both devices returned to `normal`, and a bounded 4096x4096 matmul passed on
each with no further kernel events. This is the same failure class as the R116
attempt-1 reset on `0000:03:00.0`. The boot has now reset both cards, so no
further 27B server was launched on it; the clean reboot should come before any
further lane run.

### R120-R120e: oneDNN runtime-M experiment (closed for serving)

Location: `csrc/xpu/onednn/onednn_ext.h`, `matmul_primitive_cache_t::get`, at
kernel commit `1e90ffa672ba02f17a909da11838a4c55b199783` (the image's kernel
head, present in `/home/steve/src/vllm-xpu-kernels`; use a fresh isolated source
directory or clone, not a secondary Git worktree, because the main checkout
carries unrelated uncommitted work and repository policy forbids secondary
worktrees). The primitive is built from
concrete `{m, k}` / `{m, n}` memory descriptors and cached under a key that
includes `m`, so oneDNN selects a kernel per M. Change, for the W8A16 path
only: build `src_md` and `dst_md` with `DNNL_RUNTIME_DIM_VAL` in the M
position, drop `m` from the cache key, and pass memory objects carrying the
real dims at execution. Rebuild `_xpu_C.abi3.so` with the lane's
`build-vllm-xpu-kernels-xpu-c-only.sh` settings, inject it as the R83
Dockerfile does, and rerun the three census scripts. The gate required every
shape collapses to one row-0 class over M 1-512, permutation invariance holds
at every M, the 168-256 nondeterminism is gone, and the decode plateau cost is
measured. If oneDNN rejects runtime dims with block scales, the fallback is the
Triton row-invariant GEMM or fixed 32-row chunking.

R120e proved the numerical mechanism and rejected it for service. After four
pre-execution build corrections (descriptor width, cache-key type, SYCL SONAME,
then Torch C++ ABI), the exact-R62-image build loaded and passed a bounded
smoke. All six production W8A16 shapes had one row-0 class for every tested M
from 1 through 512; all prefix, permutation, pad-content, and repeat checks
were bitwise exact. The denser determinism sweep reported zero nondeterministic
M values for all six shapes, including the 168-256 region. The diagnostic
W8A16 head also had one class.

The cost is prohibitive. At M=2 the runtime-shape primitive took 1.884-5.186 ms
per production call. Ratios against the static census were 16.8x-122.8x; the
properly warmed attention-QKV comparison is about 47x (3.054 ms versus 64.8
us). No serving image or 27B server was launched. This implementation is
closed: oneDNN's generic runtime-shape path is a useful correctness reference,
not a deployable kernel.

The unchanged FP16 head stayed repeat-deterministic for fixed inputs but had
four row-0 classes across the sweep (observed groups spanning 1-32, 33-128,
136-320, and 328-512). A deployable row-invariant kernel therefore remains the
next identity task, and the wider prompt-length endpoint gate remains required.
See the [structured R120e result](../data/2026-09-02-qwen38-fp8-w8a16-runtime-m-r120e-result.json).

### R121: fixed-tile Triton W8A16 screen (closed)

A direct Triton reference used a fixed 16-row program tile, FP32 accumulation,
and the checkpoint's 128x128 FP32 block scales. All three tested configurations
compiled on B70 for the K3072/N5120 and K5120/N7168 attention shapes. Every
configuration produced one row-0 class from M=1 through 256, was bitwise exact
under an M31 permutation and an M59 repeat, and differed from static oneDNN by
only `0.0001220703125` maximum at M16.

The fastest configuration (`BLOCK_N=128`, `BLOCK_K=64`, eight warps) still took
348.757 us at M2 for attention output and 351.736 us for attention QKV: 26.20x
and 5.64x their paired static oneDNN calls. The arithmetic design is a valid
row-invariant reference, but this Triton lowering is closed for service. No
server was launched. See the [R121 result](../data/2026-09-02-qwen38-fp8-w8a16-triton-row-invariant-r121-result.json).

### R122/R122b: fixed-M4 batched oneDNN screen (closed)

R122 encoded activations as `[B,4,K]`, a shared weight as `[1,K,N]`, and block
scales over the last two weight dimensions. The first attempt safely failed
before GEMM because oneDNN accepts exactly two scale-group dimensions, not a
rank-sized vector. R122b corrected only that API detail.

R122b was fast: across B1, B8, B32, and B64 its attention-output latency was
0.99-1.14x the natural flattened call, and attention QKV was 1.00-1.02x. It was
not row invariant. Attention output formed six row-0 classes as B varied and
failed an arbitrary B32 row permutation; QKV formed five classes. Only B1 was
bitwise equal to independent static M4 calls. Thus oneDNN still selects
B-dependent arithmetic even when the logical per-batch M is fixed. A viable
oneDNN solution must pin its implementation/reduction strategy, not merely a
descriptor dimension. No server was launched. See the
[structured result](../data/2026-09-02-qwen38-fp8-w8a16-fixed-m4-batch-r122b-result.json).

### R123-R126a: pinned oneDNN JIT strategies (closed)

An exact dev-mode rebuild of the pinned kernel and oneDNN commits exposed the
selected JIT strategy string. Natural M4 and M32 strategies made both attention
shapes exact across M=1-512, prefixes, permutation, repeat, and padding content;
the M256 strategies did not. Interpolation found one useful additional point:
the natural M128 strategy was exact and fast for K=5120 shapes. Across all six
production shapes, M32 was exact everywhere and M128 was exact only at K=5120.
The selected direct catalog nevertheless missed the frozen latency gates on
four shapes (geometric ratios 1.251 and 1.308 for GDN-in and gate-up; worst
ratios 1.564 and 1.756 for GDN-out and down-proj).

Combining fixed-M batching with a pinned strategy proved the mechanism more
strongly but did not rescue latency. Fixed-M4 plus the M32 strategy was exact
but cost 1.126-1.318x geometrically and up to 1.770x. R126 initially stopped at
the inherited explicit `[B,4,K]` guard; the sole preregistered R126a correction
changed that guard to `[B,32,K]`. The corrected fixed-M32 candidate was exact
for both representative shapes under every row, M512-prefix, sequential-M32,
M200-permutation, M200-repeat, and random-pad-content check. Against natural
flattened oneDNN it cost 1.333x geometrically / 1.667x worst for attention
output and 1.235x / 1.859x for attention QKV, failing both frozen gates.

This closes the entire oneDNN descriptor/strategy composition family. Do not
search more source-M values, hand-tune strategy strings, or combine more fixed
descriptor dimensions. The next implementation is a purpose-built kernel with
a fixed per-output K reduction and M/N affecting only independent grid counts.
See the [R126a structured result](../data/2026-09-02-qwen38-fp8-w8a16-fixed-m32-pinned-jit-r126a-result.json).

R134 checked one remaining composition that R124's per-shape aggregate gate did
not answer: source-M32 for small rows and source-M128 for large rows. Existing
timings predicted that blend would clear both latency gates on every K=5120
projection, and both frozen strings visibly contained `k128`. A digest-only
screen therefore compared the complete outputs from fresh M32 and M128
processes on all six shapes and all 15 registered M values.

The result was unambiguous: zero of 90 shape/M pairs matched, including row 0.
This was true even on K=5120, where each strategy separately passed every
internal invariance check. The shared `k128` token does not specify the complete
floating-point accumulation grouping. Switching stable strategies by M would
simply create two different stable answers and restore the identity hole. No
dynamic selector was built and no server was launched. See the
[R134 result](../data/2026-09-02-qwen38-fp8-w8a16-pinned-jit-cross-digest-r134-result.json).

### R135: decode-weighted invariant-M32 ladder (c1-c32 pass, c64 fail)

R135 tested the only remaining single-strategy compromise with an A-B-B-A
process order per shape, deeper timing, and the actual 64-layer call graph:
48 each of GDN-in/out, 16 each of attention-QKV/output, and 64 each of MLP
gate/up and down. MTP1 maps c1-c64 to target-forward M values 2-128.

Both candidate replicates retained every identity check on all shapes. Weighted
latency was better than natural oneDNN at c1/c2 and stayed within `0.4%` through
c32: ratios for M2/4/8/16/32/64 were `0.948`, `0.956`, `1.003`, `1.001`,
`1.003`, and `0.998`. At M128/c64 it rose abruptly to `1.330`, failing the 3%
decode gate. The prompt-shape cost is also material: `1.621x` weighted at M168
and `1.926x` at M256.

This rejects a uniform M32 source build, but narrows the engineering target.
The exact arithmetic is already fast through M64; the missing kernel must
recover M128 scheduling efficiency while remaining bitwise equal to M32, not
invent another reduction. No server was launched. See the
[R135 result](../data/2026-09-02-qwen38-fp8-w8a16-pinned-m32-decode-ladder-r135-result.json).

### R127: Xe2 CUTLASS fixed-M32 BLOCK_FP8 (mechanism accepted)

The exact pinned kernel source already contained an Xe2 grouped-GEMM BLOCK_FP8
path matching the checkpoint's FP16 activations, E4M3 weights, and FP32
`[K/128,N/128]` scales. R127 invoked it with one logical expert and pinned the
existing `w8a16_policy_m_32` (`32x64x32`) for every M. The stock build's full
MoE instantiation exceeded the 16-GiB host, so a separately recorded build-only
patch instantiated just this exact datatype/policy combination.

Both representative attention shapes produced one row-0 class across all 15
tested M values from 1 through 512. Every M was bitwise equal to the matching
M512 prefix; M200 permutation and repeat checks passed; appending 32 random
rows to M168 changed no existing output. Maximum error versus natural oneDNN
was `0.00006103515625`, one FP16 ULP. This is the first specialized kernel in
the campaign to prove the required arithmetic while remaining near the
performance envelope.

The one-expert grouped wrapper is not itself deployable. Attention QKV passed
the frozen latency gate at `1.029x` geometric mean and `1.214x` worst, but
attention output measured `1.436x` and `1.780x`. The wrapper allocates an atomic
scratch tensor per call and launches a persistent all-SM MoE scheduler even for
one dense matrix. The next justified experiment keeps the identical GEMM body
and fixed K reduction but launches exactly `ceil(M/32)*ceil(N/64)` independent
tiles, eliminating the rows tensor, atomic scratch, and persistent scheduler.
No model server was launched. See the
[R127 result](../data/2026-09-02-qwen38-fp8-w8a16-cutlass-fixed-m32-r127-result.json).

### R128: direct exact-tile grid (overhead attribution closed)

R128 kept R127's exact `xe_gemm_4bits<BLOCK_FP8,128>` body and M32 policy but
launched exactly `ceil(M/32)*ceil(N/64)` workgroups. It removed the device rows
read, per-call atomic tensor allocation, global atomic work queue, and
persistent all-SM scheduler. Identity and one-ULP numerical results were
unchanged.

Latency barely moved. Attention output improved from `1.436x` to `1.389x`
geometric mean and remained `1.757x` worst; QKV moved from `1.029x` to `1.005x`.
The allocation/scheduler hypothesis is rejected. The next narrow test is the
source's M16 policy for small M, gated on bitwise equality to the accepted M32
arithmetic. No server was launched. See the
[R128 result](../data/2026-09-02-qwen38-fp8-w8a16-cutlass-direct-grid-r128-result.json).

### R129: M16 small-row policy (safe composition, mixed gate)

Selecting the existing M16 tile for M<=8 and M32 otherwise remained bitwise
equal across the policy boundary. QKV improved to `0.947x` geometric mean and
`1.189x` worst versus natural oneDNN. Attention output improved to `1.350x`
and `1.668x`, still outside both gates. This uniform candidate is closed, but
the M16/M32 CUTLASS path is now a valid component for the larger-K shapes.

The next screen is heterogeneous rather than another global policy: use the
already exact and fast pinned-oneDNN M32 strategy for K3072/N5120, CUTLASS for
the K5120 shapes, and measure CUTLASS at K8704/N5120. No server was launched.
See the [R129 result](../data/2026-09-02-qwen38-fp8-w8a16-cutlass-m16-small-r129-result.json).

### R130: heterogeneous all-shape catalog (one shape remains)

CUTLASS remained row/prefix/permutation/repeat/random-append exact on all six
production shapes and stayed within `0.0001220703125` of oneDNN. Combined with
R124's pinned-oneDNN M32 result for K3072/N5120, the catalog now covers GDN-in,
both attention projections, and MLP-down inside their shape gates. Only the
very wide K5120/N17408 MLP gate/up projection remains: it measured `1.180x`
geometric and `1.673x` worst, with M168 at 977.2 us versus 583.9 us.

The next change is confined to that shape and preserves K32 reduction order:
double the M32 tile's N width from 64 to 128 and its N subgroup count from four
to eight. No server was launched. See the
[R130 result](../data/2026-09-02-qwen38-fp8-w8a16-heterogeneous-catalog-r130-result.json).

#### Post-R132 layout correction

R127-R132 constructed `weight_nk.t().contiguous()`, while production's
`XPUW8A16ScaledMMLinearKernel.process_weights_after_loading` deliberately
stores `weight_nk.t()` as a non-contiguous `[K,N]` view with
`stride[-2] == 1`. The earlier R123/R124 census used that production NT
layout. This accounts for large control-latency differences (gate/up large-M
oneDNN was roughly twice as slow in the contiguous-layout screen).

The fixed-K arithmetic proofs remain valid, including all row and policy
boundary checks, but the R130 catalog latency assignments are suspended. R133
must reinterpret the same physical `[N,K]` storage with the kernel's row-major
B layout and compare against oneDNN's actual NT path before any integration.

### R133: production-NT CUTLASS correction (closed)

R133 made that correction explicitly. Both the CUTLASS candidate and natural
oneDNN control consumed the production noncontiguous `[K,N]` transposed view,
with strides `[1,K]` over physical row-major `[N,K]` checkpoint storage. The
candidate wrapper interpreted that same physical storage as row-major B; the
patch chain reproduced the built source byte-for-byte and passed a no-device
ABI/registration preflight in the exact R62 image before XPU execution.

Arithmetic remained excellent: all six production shapes had one row-0 class,
were exact against every M512 prefix, and passed M200 permutation/repeat plus
M168 random-appended-row checks. Maximum error against oneDNN was
`0.000244140625`.

Performance decisively rejected the candidate. No shape passed both frozen
latency gates. Geometric candidate/control ratios were `1.883` GDN-in, `2.023`
GDN-out, `1.430` attention-QKV, `1.584` attention-output, `1.879` gate/up, and
`1.279` down-projection; worst points ranged from `1.806x` to `3.859x`. This
supersedes every R127-R132 catalog assignment while retaining their arithmetic
proofs. The existing Xe2 CUTLASS BLOCK_FP8 tile family is closed for production
unless a materially different matrix engine, end-to-end-cheaper layout, or
upstream kernel change appears. No server was launched, both devices remained
normal, and no new Xe fault was logged. See the
[R133 result](../data/2026-09-02-qwen38-fp8-w8a16-production-nt-r133-result.json).

### Clean-boot R119 update

After the required reboot, R119 promoted the R62 single-user profile at a
`54.424603 tok/s` two-server center, with all A/B and candidate/MTP0 complete
arrays 12/12 exact on the fixed 48-78-token-prompt suite. Both B70s passed
per-card compute and two-rank XCCL before and after the campaign; the boot
remained free of Xe faults.

The same endpoint probe on the exact promoted image strengthened the boundary:
168 prompt tokens produced two distinct 64-token streams across five repeats,
not merely five distinct logprob arrays. The 200/224/250-token cases retained
one token stream but five logprob arrays each; 100 and 300 remained bitwise
repeatable. The runtime-M experiment is therefore the immediate next lane step,
and success must remove both the operator digest variation and this endpoint
token divergence before any broader determinism claim.

See the [R119 promotion](2026-09-02-qwen38-fp8-mtp1-draft-int4-r62-cleanboot-r119-promotion.md)
and [structured result](../data/2026-09-02-qwen38-fp8-mtp1-draft-int4-r62-cleanboot-r119-result.json).

## Reporting boundary

Operator diagnostic and review only. Census timings are single-GPU,
random-data screening numbers with no TP collective and must not be quoted as
lane performance. No README, website, package, or LocalMaxxing change.
