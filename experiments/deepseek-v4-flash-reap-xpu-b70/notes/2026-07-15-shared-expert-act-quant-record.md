# Exact shared-expert activation/quant fusion record

## Outcome

The TP4 single-session DeepSeek V4 Flash K160 record increased from
`33.433875` to **`34.067121 tok/s`** (`+1.89%`). A paired strict cold suite
reached `34.049735 tok/s`. LocalMaxxing approved the promoted result as
`cmrlf1hn609glmj019rsjdl4r`.

Evidence is under
`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/shared-expert-fused-act-quant-20260715T0140Z`.
The exact source identities are vLLM `38260cda833367a8dbf4896679d93f9d5da74f95`
and XPU kernels `ae815123408603bb45b5df4d745be8375cf1985c`.

## What was fused

Every one of the 43 decoder layers previously materialized the shared-expert
clamp-at-10 SwiGLU result and then launched dynamic per-128 FP8 activation
quantization before the W8A8 shared-down projection. The new guarded M=1 XPU
path combines those operations in one Xe2 kernel and feeds the existing
block-FP8 GEMM directly.

This fusion is numerically deliberate. It retains the BF16/FP16 rounding
boundaries after clamp, sigmoid input/output, gate multiply, up bias, and final
multiply. Quantizing a collapsed FP32 expression would change FP8 scales and
bytes. Eight device tests across two B70s, BF16/FP16, and E4M3FN/E5M2 required
bitwise-identical quantized values and FP32 scales; all passed.

The isolated `[1,1024] -> [1,512]` boundary improved from a median `77.326 us`
to `15.462 us`, a `5.00x` speedup and a direct-launch projection of `2.660 ms`
over 43 layers. Full graph replay already amortizes some host launch cost, so
the measured end-to-end gain was smaller but still repeatable and record-worthy.

## Promotion evidence

- strict cold suites: `34.067121` and `34.049735 tok/s` median for generated
  tokens 1-100 after TTFT;
- all 24 suite rows reported `cached_tokens=0`;
- changed-input replay: `1073 -> 437 -> 1073`;
- exact-copy, Paris, and strict-JSON canaries passed;
- executable frozen quality gates passed;
- the frozen 768-token invariant returned `101! - 1`;
- no speculation, prefix caching, response reuse, history acceleration, or
  context checkpoints were enabled.

The public K160 checkpoint's already documented intermittent multilingual
corruption remains visible in the broader quality capture. It affected the
code-debug and math-invariant text in this run, while the executable gates and
required invariant answer remained correct. This limitation is disclosed in
the LocalMaxxing payload and is not attributed to the fusion.

## Iteration-cache lesson

The first editable kernel build attempted a slow full GitHub oneDNN clone even
though the exact oneDNN commit (`80afa71049cd69a3df32adcccb623b12cd7baa22`)
already existed locally. Populating `.deps/onednn-src` from the matching local
Git object store avoided the download. The initial dependency/XPU build took
about eight minutes; its oneDNN objects and generated kernels now remain in the
worktree for incremental source rebuilds. Future kernel lanes should preserve
this `.deps`/`build/temp` cache rather than recreating dependency state.

## Next boundary

This fusion removes only one activation/quant family. The next high-value lane
is the M=1 MHC post/pre producer fused with exact RMSNorm. It occurs at 85
useful K4096 boundaries per token and can remove the standalone RMSNorm launch
and its global-memory producer reread.

The promoted selective-W8A16 shape list means both K4096 projection consumers
currently use BF16 activations and bypass dynamic FP8 activation quantization.
Dual E4M3FN/FP32-scale output is therefore not part of the first experiment;
adding it would create unused work. It becomes relevant only if a later
isolated crossover shows fused-prequantized W8A8 beats the current W8A16
projection families without losing the quality invariant.
