# Qwen3.8 AutoRound packed-GDN ordinary-code-shape candidate

Date: 2026-08-18

Status: source-verified candidate; not built or run; no speed or quality claim

## Motivation

The strict MTP3 configuration is self-deterministic on 25/25 prompts but
measures `91.926 tok/s` all-25 and `86.720 tok/s` on selection-12. A fast arm
measured `98.222/98.717 tok/s` all-25 but reproduced only 12/25 outputs. That
arm disabled both serial-exact GDN and global batch invariance, so neither the
speed delta nor the divergence is causally assigned yet. The separate
factorial diagnostic must resolve that confounder.

There is nevertheless a useful operator-level fact. Historical direct checks
of `gdn_attention_spec_decode` found its packed SSM/core results numerically
close but not bit-identical to four repeated calls to ordinary
`gdn_attention`, including with FP32 state. The serial-exact production mode
gets ordinary-kernel arithmetic by launching the ordinary recurrent kernel
once per verifier row, four times per GDN layer. The packed implementation
keeps all four rows in one launch but its compile-time loop and expression
shape differs from the ordinary kernel even though the recurrence is
mathematically the same.

## Candidate

Patch:
[`../patches/vllm-xpu-kernels-qwen38-packed-gdn-ordinary-code-shape-candidate-20260818.patch`](../patches/vllm-xpu-kernels-qwen38-packed-gdn-ordinary-code-shape-candidate-20260818.patch)

- XPU-kernels base: `2dd55f380df753a10a88fcd9e96192561066e713`
- patch SHA256: `e4f46edcfd949768e1b124dfd57bd076c17835b35cbc22ed2ab6ad646e1aa1b6`
- changed file: `csrc/xpu/gdn_attn/spec_decode.hpp`
- scope: only `gated_delta_rule_spec_kernel`

The patch makes the packed kernel textually match ordinary
`gated_delta_rule_kernel` where arithmetic code generation can differ:

- fixed-size state, K-bucket, and V-lane loops receive the same unroll
  directives;
- A-log, dt-bias, beta, decay, Q/K/V loads, and output conversion use the same
  expression form and local mutability as the ordinary kernel; and
- launch topology, state-column semantics, FP32 accumulation, subgroup-32
  reductions, and mathematical operations remain unchanged.

This is intentionally a whole-candidate source delta, not a promoted default
or an environment door. A separate build is required.

## Fail-closed validation order

First prove that the existing binary fails the strict oracle, so the test is
sensitive. Then rebuild the candidate and require it to pass on each physical
B70. Use the actual Qwen3.8 per-rank production dimensions: global K/V heads
16/48 under TP2, K/V dimensions 128/128, four packed MTP3 verifier rows, FP16
activations, FP32 SSM state, three extra speculative convolution positions,
and poisoned physical SSM-row padding.

```bash
repo=$(git rev-parse --show-toplevel)
export VLLM_TARGET_DEVICE=xpu
export PYTHONPATH="/path/to/candidate/vllm-xpu-kernels:/path/to/vllm${PYTHONPATH:+:$PYTHONPATH}"
export LD_LIBRARY_PATH="/path/to/candidate/vllm-xpu-kernels/vllm_xpu_kernels:/path/to/venv/lib/python3.12/site-packages/torch/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

for device in xpu:0 xpu:1; do
  python "$repo/scripts/check-gdn-native-spec-prefix.py" \
    --kernel-repo /path/to/candidate/vllm-xpu-kernels \
    --device "$device" --num-reqs 1 --spec-len 4 \
    --num-k-heads 16 --num-v-heads 48 --tp-size 2 \
    --head-k-dim 128 --head-v-dim 128 --width 4 \
    --dtype fp16 --ssm-dtype fp32 \
    --spec-conv-extra-state-len 3 --ssm-row-padding-elements 64 \
    --require-bit-exact \
    --json-out "/path/to/evidence/packed-ordinary-shape-${device//:/-}.json"
done
```

Do not add `--exact-recurrent` to this screen: the subject is the fast packed
kernel, while repeated ordinary decode is the reference. The checker covers
fresh rows, every accepted-count restart for one request, a second token
window, and a literal two-call full-accept restart. Any nonzero SSM/core diff,
padding mutation, missing output, crash, or nonzero exit rejects the candidate.

Only after both devices pass bit-exactly should the measuring host run:

1. the published global-batch-invariant/GDN factorial arm;
2. a candidate fast-packed arm with global batch invariance retained;
3. two complete cold 25-prompt A/B runs with 25/25 token equality;
4. the new Qwen3.8 target-only quality oracle and semantic/long-context gates;
5. matched performance reporting for all-25 and selection-12.

The source patch alone does not establish bit identity. Compiler code shape is
the hypothesis, and the direct oracle is the required decision gate.
