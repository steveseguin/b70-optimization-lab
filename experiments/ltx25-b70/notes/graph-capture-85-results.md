# Packet 85: the QKV fusion arm is retired — incompatible with the shard, and the win is gone (2026-09-20)

Packet 85 added one arm, `pipe-fuse2-tsh` (the fusion gate's designed `fused`
mode on the 23/25 two-clip sharded sampler). The warm arm failed before
producing a clip:

```
RuntimeError: Expected all tensors to be on the same device, but got mat1 is
on xpu:0, different from other tensors on cpu (ltx_qkv_fusion.py:71, F.linear)
```

## Why it fails

`FusedGroup.__init__` stacks the projections' weights with `torch.cat` at
install time. The fusion gate executes before the shard model is resident, so
the stacked tensor is built on CPU — and because the stack lives outside the
module tree, neither the shard loader nor model_management ever moves it. The
first block forward then meets a CPU weight against an xpu activation.

The adapter predates the layer shard (it was written when the whole model
lived on one card and ComfyUI moved it as a unit). It was never executed on
the real model: the only fusion arm before packet 85, `graph-fused`, appears
in no campaign results.

## Why it is not worth fixing

1. **The rationale shrank.** The adapter's docstring justifies fusion by the
   ~28 us fixed launch overhead of many small GEMMs. Graph capture already
   removes launch overhead: captured blocks replay kernels without per-kernel
   dispatch. What remains is kernel-side efficiency of stacked GEMMs, roughly
   5 fewer kernel instances per block x 48 blocks — on the order of 1% of the
   2.65 s pair time, not the ~10% class.
2. **The memory does not fit.** Fusing duplicates the stacked weights
   (originals are retained for exact restore): 4.12 GiB over 48 blocks, about
   2.0 GiB on xpu:0's 23 blocks. The f84 sampler receipts show xpu:0 at
   30.45 GiB reserved of 32.6 — the duplication does not fit without freeing
   the originals, which breaks the install-time bit-for-bit proof structure.

A device-following lazy stack with free-after-proof could fix both, but the
expected ~1% does not justify redesigning an exactness-critical adapter. The
arm row is removed from the preparer; the gate stays in its pass-through
`original` mode in every graph. Server 85's failed-warm receipts are in
`encoder-server-graph-capture-85/`.

## What the failed run bought

The fusion detour produced the gap analysis that ranks the real next lever
(`graph-capture-84-results.md` §2, refined by the f84 sampler receipts):

- The sampler node returns in 58 ms; the two sample workers are the pacer,
  each pair-job measuring 2.654 s against a 3.26 s/pair wall period — a 23%
  interleave loss, not feed starvation (`pending_after` is 4 jobs at every
  submission; `queued_ahead` 28/28).
- Per-card reserved memory: xpu:0 30.45, xpu:1 26.03, xpu:2 23.19, xpu:3
  17.88 GiB. xpu:0 is the memory-critical card; any new resident state must
  go elsewhere.
