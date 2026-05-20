# MiniMax XPU FlashAttention No-Contiguous Patch Note

Date: 2026-05-20

## Purpose

Reproduce upstream vLLM's XPU FlashAttention cleanup on the current MiniMax
M2.7 AutoRound TP4 high-speed stack.

The patch removes forced contiguous conversions immediately before
`flash_attn_varlen_func`:

```diff
-        # In encode attention, k and v maybe not contiguous and current
-        # kernel can't handle it
-        if block_table is None:
-            k = k.contiguous()
-            v = v.contiguous()
         return flash_attn_varlen_func(
             out=out,
-            q=q.contiguous(),
+            q=q,
             k=k,
             v=v,
```

This mirrors upstream vLLM commit `be0dcc29d`, `[XPU] remove q/k/v force
contiguous for flash_attn (#40356)`.

## Files Patched Locally

- `/home/steve/src/vllm/vllm/_xpu_ops.py`
- `/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/vllm/_xpu_ops.py`

Only the FlashAttention hunk above is part of this candidate. The same file
also contains earlier Gated DeltaNet speculative decoding fixes; those are
pre-existing local patches and not part of this result.

## Validation

Import and py_compile passed before benchmarking.

Strict MiniMax quality passed:

- raw145 n64 exact
- raw145 n256 exact
- semantic suite
- arithmetic repeat n64/r8
- extended sixpack n64/r2

Performance did not improve:

- Promoted baseline: `89.314195` output tok/s, `119.085594` total tok/s
- Candidate mean: `88.890310` output tok/s, `118.520414` total tok/s

Decision: keep as a documented upstream-compatible cleanup, but do not promote
and do not submit to LocalMaxxing.
