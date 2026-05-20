# MiniMax XPU FlashAttention No-Contiguous Retest

Date: 2026-05-20

## Summary

Tested the upstream vLLM XPU FlashAttention change that removes forced
`q.contiguous()`, `k.contiguous()`, and `v.contiguous()` before
`flash_attn_varlen_func`.

This is quality-clean on the current MiniMax M2.7 AutoRound TP4 recipe, but it
does not improve throughput. Keep it as an upstream-compatible cleanup, not as a
MiniMax performance promotion.

## Candidate

- Label: `minimax-xpu-flash-no-contiguous-currenthigh-20260520`
- Model: `Lasimeri/MiniMax-M2.7-int4-AutoRound`
- Hardware: 4x Intel Arc Pro B70 32GB
- Runtime: vLLM `0.20.1-local`, XPU/Level Zero, TP4
- Shape: p512/n1536, ctx2048, batch 1, `max_num_batched_tokens=512`, `block_size=256`
- Candidate code: remove forced contiguous conversions in `vllm/_xpu_ops.py` XPU FlashAttention path.
- Source basis: upstream vLLM commit `be0dcc29d`, `[XPU] remove q/k/v force contiguous for flash_attn (#40356)`.

## Quality

Full strict quality passed:

- raw145 n64 exact hash: `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- raw145 n256 exact hash: `58f6e8251c7a0a17e8c441278b5861f7d5da914fa1823ecd10484b296f2d7537`
- semantic suite hash: `adacbf144264486ea7d378ebb6a4c0ba23951b72c4cf86251a762b07ebef5805`
- extended sixpack hash: `1e3560554f57b2b56cec8f49f28bc8ba12e9e0ced26bdc99a976f1433c99caa7`

The arithmetic repeat gate passed determinism and semantic checks. The strict
script used the shorter `r8` arithmetic repeat mode for this run, so its
combined repeat hash is not the promoted `r16` hash.

## Performance

Promoted baseline:

- Output: `89.31419538094708` tok/s
- Total: `119.08559384126276` tok/s

Candidate four-repeat result:

- Output mean: `88.89031035563913` tok/s
- Total mean: `118.52041380751884` tok/s
- Output repeats: `89.13685773856997`, `89.20795559193768`, `89.17697295819154`, `88.03945513385735`
- Total repeats: `118.84914365142662`, `118.94394078925022`, `118.90263061092206`, `117.38594017847646`

Delta versus promoted:

- Output: `-0.42388502530795` tok/s, about `-0.47%`
- Total: `-0.56518003424392` tok/s, about `-0.47%`

One benchmark repeat printed the existing shutdown noise:

```text
Bad address (src/pipe.cpp:367)
!!!!!!! Segfault encountered !!!!!!!
```

This noise has appeared in prior quality-clean runs, but the lower mean and
slow fourth repeat make this candidate a clear no-promotion result.

## Decision

Do not submit to LocalMaxxing. Do not treat this as a speed improvement.

The useful learning is that removing the XPU FlashAttention contiguous copies is
not enough to move MiniMax decode throughput. The remaining bottleneck is still
in the repeated MiniMax TP collective / Q-K RMS / attention or MoE boundary
families, not this FlashAttention wrapper copy path.

## Artifacts

- Strict summary: `/home/steve/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-xpu-flash-no-contiguous-currenthigh-20260520-strict-tp4-ctx2048-mbt512-bs256-20260520T035915Z-summary.json`
- Quality directory: `/home/steve/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-xpu-flash-no-contiguous-currenthigh-20260520-strict-tp4-ctx2048-mbt512-bs256-20260520T035915Z-quality`
- Local data: `data/minimax-m27-xpu-flash-no-contiguous-negative-20260520.json`
- Patch note: `patches/minimax-xpu-flash-no-contiguous-negative-20260520.md`
