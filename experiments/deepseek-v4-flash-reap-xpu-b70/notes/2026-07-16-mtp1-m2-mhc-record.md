# DeepSeek V4 K160 MTP1 native M=2 MHC record

Date: 2026-07-16

## Outcome

A native fixed-shape M=2 MHC post/pre kernel produced a new four-B70,
single-session target-verified record:

- headline confirmation: **60.264242 tok/s**, p10 **56.243105**;
- independent screen: **59.291531 tok/s**, p10 **56.500724**;
- previous record: **57.412142 tok/s**;
- headline improvement: **4.97%**;
- 70/70 ordered exact capture suites pass, including positions 28 and 58 after
  both strict suites;
- every realistic and exact request reports `cached_tokens=0`;
- LocalMaxxing: `cmrmvjbok1np3mj01p9il8486` (`APPROVED`).

Evidence is under
`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/mtp1-m2-mhc-single-kernel-candidate-20260716T0210Z`.
The four-card microgate is under
`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/m2-mhc-single-kernel-microgate-20260716T0205Z`.

## What was actually wrong

The M=1 path already fused MHC post, the next pre-mix projection reduction,
Sinkhorn normalization, and layer-input production into one 256-thread Xe2
kernel. The M=2 target verifier fell back to the generic implementation, which
materialized the same boundary as three graph operations at every decoder
layer. Calling the M=1 kernel twice was not a solution: two command submissions
were slower than the generic M=2 path.

The repair generalizes the proven M=1 kernel to a compile-time token count.
For M=2, one command launches two independent 256-thread workgroups, one per
verifier row. Each workgroup retains the M=1 reduction order, BF16 rounding
points, local memory, and arithmetic. Only token offsets and the global range
change. The public operator rejects anything outside the exact K160 contract:
BF16 `[2,4096]` input, BF16 `[2,4,4096]` residual, FP32 mix/projection tensors,
contiguous storage, HC4, and the existing 24-by-16384 projection matrix.

Source identity:

- vLLM `9cf403e516566b44bbfcc7ad00eef976867c861b`;
- XPU kernels `46b95e64a315e04002e071640e8855b2398ab1ec`;
- oneCCL `48fda4f0e074db005596d6899d5227d3f0316c12`;
- new default-off flag `VLLM_XPU_V4_MHC_POST_PRE_M2_SINGLE_KERNEL=1`.

The previously tested modular-MoE output alias remains off. It was exact but a
noise-floor negative, so it is not part of this record.

## Hardware and model gates

All four B70s passed 40 changing eager epochs and eight changed-input graph
replays with zero mismatches in residual, post mix, combination mix, or layer
input. Across the actual 85-boundary chain, the candidate saved:

- card 0: `969.095 us`;
- card 1: `970.719 us`;
- card 2: `962.995 us`;
- card 3: `961.639 us`.

The slowest-card saving is therefore **0.962 ms per MTP1 cycle**, comfortably
above the 0.50 ms integration gate. The two-M1-call control was explicitly
rejected; the gain comes from one submission containing two workgroups, not
from row-wise decomposition.

Inside the full model, 70 ordered exact suites produced 420 exact answers with
no mismatch or cached prompt token. The two fixed realistic suites each sent
12 unique prompts once, generated 128 tokens, retained streamed token IDs, and
passed the cold-response gate. Accepted speculative tokens remain verified by
the unchanged target model.

## Why this matters

This is a clean example of small exact fusions adding up after the larger wins:
roughly one millisecond removed from the verifier cycle became a repeatable
1.9-2.9 tok/s whole-model improvement. It also validates the right M=2 design
rule for Xe2: preserve per-row arithmetic and batching, but collapse command
submissions. Do not replace grouped M=2 expert work with two M=1 calls.

The public 12-prompt suite remains a continuity/record gate because it has been
used repeatedly. It is not sufficient by itself to promote deeper or routed
speculation; that work remains governed by the freeze-before-reveal held-out
contract in `../quality/spec-eval-contract-v1.json`.

## Next action

Use this exact source and service identity as the new performance floor. The
next bounded candidates are M=2 QNorm/RoPE/direct-KV insertion and exact M=2
in-place all-reduce, followed only by fusion packages whose combined measured
saving can survive reusable-graph execution. Preserve the native M=2 MHC flag
in every control and reject row-wise two-M1 substitutions.
