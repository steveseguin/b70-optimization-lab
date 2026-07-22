# Laguna S 2.1 DFlash accepting and FP8-KV result — 2026-07-22

## Result first

The missing paged-decode policy
`16,128,64,false,false,false` is compiled and independently gated on all four
Arc Pro B70s. The original supplied drafter was then proven incompatible with
the INT4 target: it was the plain BF16 `Laguna-S-2.1-DFlash` checkpoint, while
the INT4 target card requires `Laguna-S-2.1-DFlash-INT4`. The plain draft still
accepted `0/8,449` proposals after the kernel fallback was removed. The matched
draft was downloaded at pinned Hugging Face revision
`5e07c246915c86dc6920fead03d019989224f2ba` to the external Corsair drive and
immediately restored real acceptance.

| Mode | Median tok/s, tokens 1-100 after TTFT | p10 | Cold accepted/proposed | Mean accepted draft tokens/cycle | Cache tokens/card | Correctness |
|---|---:|---:|---:|---:|---:|---|
| target-only PIECEWISE, BF16 KV | 19.401885 | 19.238855 | n/a | n/a | 178,108 | deterministic control |
| matched DFlash m7 PIECEWISE, BF16 KV | **48.980858** | 33.931400 | 953/1,953 = **48.797%** | **3.4158** (4.4158 emitted/cycle) | 110,995 | coherent/cache-zero, not token-exact vs q=1 control |
| matched DFlash m7 PIECEWISE, FP8 KV | **46.956936** | 36.330257 | 960/1,932 = **49.689%** | **3.4783** (4.4783 emitted/cycle) | 221,990 | coherent/cache-zero, not token-exact vs BF16 |

The BF16-KV matched-DFlash result is 151.68% faster than the same-window
19.401885 target-only BF16 graph control (151.18% above the rounded 19.5
baseline). It reaches 11.66% of a 420 tok/s roofline or 9.51% of a 515 tok/s
roofline. It is a real speculative-throughput measurement, not the prior
fallback number, but remains diagnostic rather than promotion-safe because the
batched q=8 verifier is not exact-token identical to target-only q=1 greedy.

Explicit FP8 KV is 4.132% slower than BF16 KV in the matched-DFlash comparison.
At fixed `--gpu-memory-utilization 0.90`, it does not reduce reserved card
residency: the primary worker mean changed from 27,708,895 KiB to
27,710,099 KiB (+1,204 KiB, +0.0043%, noise). Instead, the same 5.76 GiB cache
budget holds exactly twice as many tokens, 221,990 versus 110,995. FP8 KV is
therefore capacity-safe and coherent here, but not exact-token-safe and not a
speed win.

## Kernel rebuild and four-card gate

The kernel branch was clean before editing. One line was added to
`csrc/xpu/attn/kernel_configs/paged_decode_default.conf`, then committed as:

- XPU-kernels commit: `c615c38fb79d4035118c05675565dbf7e2443a90`
  (`attn: compile Laguna DFlash decode shape`);
- compiler: `/opt/intel/oneapi/compiler/2025.3/bin/icpx`, Release/Ninja;
- build log:
  `/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/logs/build-vllm-fa2-laguna-c615c38-20260722.log`,
  SHA256 `12b2e3460f10b26be83414baa967004c3c3a343c6a0d8dd69527a5ef8923a200`;
- installed Python extension `_vllm_fa2_C.abi3.so`, SHA256
  `e6faed930bbcd7a366cc55281b99e1a8d7016a8db40ab10015d78f72937c8e64`;
- installed tuple-bearing payload `libattn_kernels_xe_2.so`, SHA256
  `680d486970eb58dc63f0b7ef41e028e2bb4b5a630a2987c96f8609d46a00e161`.

The wrapper hash is unchanged because the policy specializations live in the
payload. Both binaries have `$ORIGIN` RUNPATH. The prior installed pair was
preserved under
`.../laguna-s-2.1/binaries/fa2-bcfde2d-before-dflash/`.

The expanded seven-case changed-input oracle passed on cards 0, 1, 2, and 3,
including the q-group-16 DFlash full/non-local decode case at KV length 321.
Pass packet SHA256 values are:

- card 0: `bea1256c1f699b3f80d7943e05d45e0d95426f0f99d1398dae9996f9a2bc7597`;
- card 1: `a74a173bf778e291b5a01131fffba979f07844438918f403b8d5810e4b85c5c2`;
- card 2: `873acb815d0a3bb8aed86b4c131ac80a6265c7e458398ba3aefe2b5ebc015ee8`;
- card 3: `fd1c3b949a69061cb648f045715004c02af5e40f7b33f8dd9ab365f396ffeeb2`.

The files are
`.../logs/attention-all-tuples-plus-dflash-gate-card{0,1,2,3}-c615c38-20260722.json`.
The passing gate used `ZE_AFFINITY_MASK=<card>`; an initial invalid combination
with a multi-device `ONEAPI_DEVICE_SELECTOR` was retained as
`*.selector-error.*` rather than discarded. Neither matched-draft server log
contains the missing tuple, a `not compiled` message, or an attention fallback.

## Why the first post-rebuild run still accepted zero

With the originally supplied plain draft, the compiled-kernel BF16 run produced
1,207 verifier cycles, 8,449 proposals, and zero accepted tokens. All seven
per-position counters were exactly zero. Vocabulary size (100,352), token map,
mask ID 12, shared target embedding/lm_head, and auxiliary tap mapping
`(2,11,20,30,39,48)` were checked and matched.

The mismatch was the checkpoint family. The target INT4 model has an online
block-H128 R1 transform: embedding, attention output, and MLP output remain in a
Hadamard-rotated residual basis, while inverse transforms sit on q/k/v,
gate/up/router/g projections and the lm_head input. The plain BF16 draft has no
corresponding transform and consumes the six rotated target auxiliary states
directly. That makes its first proposal effectively unrelated to the target.
The target README explicitly requires the quantization-matched draft. The
matched model weights differ from the plain draft and have SHA256
`0850e39b5c079a9f1a9bafed729a4545b088a91876541d010d871f6d6d8bf909`;
its config SHA256 is
`6f2aac901675ce9c9a12454d0432df7609dac0bc46614ca14725ea5e86f20926`.

One terminology correction: the published DFlash configs declare
`dflash_config.causal=true`. The decode dispatch still normalizes to the
`is_causal=false` paged-decode policy named above, but that dispatch bit should
not be used to claim that the model's parallel draft block is semantically
non-causal.

## Acceptance and exactness

For the matched BF16-KV cold endpoint gate, per-position survival rates were:

`[83.871%, 67.025%, 50.896%, 43.369%, 37.276%, 30.824%, 28.315%]`.

Across the strict six-prompt performance interval, acceptance was lower but
still healthy: 551/1,596 = 34.524%, 2.4167 accepted draft tokens/cycle, with
per-position rates
`[69.737%, 50.439%, 37.719%, 28.509%, 21.930%, 18.860%, 14.474%]`.
Every request reported `cached_tokens=0`.

Standard target rejection was explicitly selected and draft sampling was
greedy. Nevertheless, exact-token comparison with the immediately preceding
target-only BF16 PIECEWISE gate fails. The repeated target-only stream begins
`[3589,604,330,2833,727,...]`; matched DFlash begins
`[3589,395,330,2833,727,...]`. A bounded live rejection trace showed the first
full draft block beginning
`[604,340,2833,727,4823,430,18573]` while the target verifier argmax rows were
`[395,330,2833,727,430,430,18573]`. Thus the first disagreement is not a
scheduler token-map error: the target's batched q=8 verification logits differ
from its q=1 incremental greedy logits. DFlash is deterministic within mode,
but this lane does not satisfy exact target-only greedy identity.

## FP8-KV correction and result

Source inspection corrected the initial assumption about `auto`: when the
checkpoint exposes an 8-bit KV scheme, vLLM resolves `auto` to calibrated FP8.
The earlier 362,929-token target-only capacity is also consistent with FP8, not
BF16. The clean comparison therefore used explicit `bfloat16` versus explicit
`fp8`.

The XPU cache-write extension accepts native BF16 only under the string
`"auto"`; an explicit `bfloat16` allocation originally failed graph warmup with
`RuntimeError: Unsupported data type of kv cache: bfloat16`. vLLM commit
`6bf7d6b83cb20c335b5e9a8ffda95d646338bbf5` normalizes native float cache dtype
names to `"auto"` only at the cache-write call, leaving the allocated cache
dtype unchanged and leaving FP8 untouched.

The explicit FP8 gate passed tokenizer integrity and within-mode determinism;
all rows were cache-zero and all quality rows had coherent shape. It is not
exact-safe: versus target-only BF16 the repeated canary first differs at output
index 11 (`81` versus `95`), and versus matched-DFlash BF16 it first differs at
index 1 (`395` versus `604`). Four of six strict-suite rows also differ between
the two KV modes. The existing bounded required-fragment completeness heuristic
failed in both DFlash modes, as it did for the target control; this is kept as a
quality caveat.

## Evidence

Headline run directories:

- BF16 KV:
  `/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/dflash-int4-piecewise-bf16-c615c38-6bf7d6b-20260722/`;
  `bench.json` SHA256
  `12aaee9e662f9a8637c07aa83ce0b9303b7d20befaa2576dd30203d351bb1054`,
  `endpoint-gate.json` SHA256
  `1b5b9738322de02c47a074a6e1cf60919228182f90aea62928afa335c05401f7`;
- FP8 KV:
  `/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/dflash-int4-piecewise-fp8-c615c38-6bf7d6b-20260722/`;
  `bench.json` SHA256
  `4c34994cce41543be70bae046b1aa68ce313d6619ceb4ece79449f3c90cff19d`,
  `endpoint-gate.json` SHA256
  `5a51ce4859d3f040e4db0ff3524eea194d5c6b8b23d29d353f0a13d02273df1`.

Both runs used TP4+EP4, 8K, PIECEWISE M=1, one active generation, depth 7,
greedy draft, standard target rejection, no prefix cache, and only external
Corsair caches/temp/output. No LocalMaxxing call or submission was made, no
DeepSeek held-out pack was used, and nothing was written to `/mnt/fast-ai`.
DeepSeek branches and all `preserve/*` tags were untouched.

## Remaining blockers and next two targets

1. Make q=8 target verification exact with q=1 greedy. The concrete first
   mismatch is verifier token 395 versus target-only token 604 at output index
   1. Audit PIECEWISE graph/attention arithmetic across target query widths and
   only promote DFlash after exact-token parity passes.
2. Fix DFlash's 512-token SWA metadata path, then reduce sparse-MoE/EP launch
   and collective overhead. `laguna_dflash.py` currently clears the attention
   wrapper's sliding window to obtain full KV allocation; metadata then
   overrides the implementation window with full attention. This is a real
   long-context correctness/performance issue even though short-prompt
   acceptance now works.

Postflight: port 18080 was closed, no vLLM/EngineCore/worker remained, and all
four B70s were free. The kernel and vLLM worktrees were clean at handoff.
