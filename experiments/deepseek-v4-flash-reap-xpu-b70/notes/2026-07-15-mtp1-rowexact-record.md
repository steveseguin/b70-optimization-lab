# DeepSeek V4 K160 MTP1 row-exact record

Date: 2026-07-15

## Result

The checkpoint-attached one-layer MTP is now a qualified TP4+EP record:

- strict headline: **50.016860 tok/s** median, 48.283807 p10;
- strict support: **49.420459 tok/s** median, 46.067979 p10;
- corrected nonspeculative base: 40.170350 tok/s;
- gain over base: **24.51%** on the headline;
- measured draft acceptance: 1,553/2,006, or **77.42%**;
- ordered exact captures: **20/20**, including ten after both long suites;
- every realistic and exact request reported `cached_tokens=0`.

LocalMaxxing approved the result as `cmrmetch81nm3mj01w1pidsyt`.

Evidence:

`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/mtp1-compressor-rowexact-graph-oneccl1712-20260715T1840Z`

## First screen was invalid

Plain MTP1 looked even faster: 50.743348 and 50.103147 tok/s across two strict
suites. It passed the first seven ordered exact captures. The eighth later
capture failed `arithmetic-b`: instead of stopping after `437`, the response
continued with prompt text. This was a real sustained graph-state failure, not
prefix caching (`cached_tokens=0`) or an output-window issue.

That screen is rejected and was never submitted. Preserve it at:

`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/mtp1-graph-oneccl1712-allreduce128k-20260715T1830Z`

The earlier eight-token strict-JSON miss is separately classified as harness
truncation: it ended with `finish_reason=length` one character before the
closing brace. All qualification captures use 16 output tokens.

## Repair and why it works

MTP1 makes the target verifier operate at M=2. DeepSeek V4's FP32 compressor
projections normally execute one M=2 `torch.mm`, whose row behavior on this
XPU graph path did not preserve the established M=1 arithmetic/state boundary.
The default-off `VLLM_XPU_V4_COMPRESSOR_M2_ROW_EXACT=1` route executes each
compressor as two M=1 FP32 projections and concatenates the results. This is
vLLM commit `25f5ac6ee0ab872b8e9ace8d299ab28aa3fc555a`, contained in the
promoted head `93fde4186`.

With the flag enabled, ten exact captures passed before the strict suites and
another ten passed after them. The latter is important: the uncorrected path
failed only after sustained request history. The repaired result therefore
has a stronger replay gate than the initial fast screen.

The model loads 25.49 GiB of weights per rank, shares the target embedding,
LM head, and top-k buffer with the draft, leaves 4,658 KV tokens at the 1K
setting, and captures the M=2 decode graph. All four workers map the selected
oneCCL 2021.17.2 runtime with SHA-256
`bf9f2e447ebb8373d7b0a41b15a32f2518a670a107d6f8fd84474798d8f2301b`.
The 128 KiB large-prefill-allreduce route remains active.

## Decision

Promote MTP1 row-exact as the current speed record while keeping the 40.170350
tok/s nonspeculative result as the base authority. The result is target
verified and is not aggregate throughput. K160 remains a hash-pruned
performance checkpoint, not the final quality-selected DeepSeek V4 pack.

The next bounded ceiling test is MTP2, which reuses the one attached MTP layer
twice. It proceeds only if exact post-load replay passes and complete-cycle
throughput beats MTP1; lower acceptance or another M=3 state defect closes it.
