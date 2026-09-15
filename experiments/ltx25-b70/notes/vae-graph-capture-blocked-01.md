# The video decoder is not graph-capturable as it stands; one host read blocks it

September15, 2026, packet22 (`prepared-encoder-graph-capture-22`), server
`encoder-server-graph-capture-22`, boot `831530c8`. **This experiment caused a
recoverable GPU fault. Read the incident section.**

## What was attempted

The video decode stage is 0.56-0.61 s and runs at 0.97-1.33 CPU core-seconds per
wall second, the same CPU-bound profile that graph capture cut 1.86x in the
sampler. `NADiffusionDecoder.forward` itself cannot be captured -- it draws `x_t`
from a generator -- but its two components are pure and each runs exactly once
per decode at `default_num_inference_steps = 1`:

- `forward_pre_diffusion(z, ...)`, the deterministic stages 1-4 NA upsample;
- `forward_diff_step(context, x_t, t)`, one diffusion step.

Packet22 added `LTXVAEGraphGate`, a composable gate that shadows those two
methods with graph-backed stand-ins and restores them afterwards, reusing the
qualified buffer, signature and bitwise-proof machinery unchanged.

The transformer arms all worked: control 3.597 s sampler, graph arm 1.920-1.953 s
sampler and 0.561-0.572 s decode, five clips, all bytewise exact. The gate node
registered and the composition is sound.

## Why it fails

The first `forward_diff_step` capture raised

```
torch.OutOfMemoryError: XPU out of memory. Tried to allocate 1044902.00 GiB.
  ltx_na_axis_candidate.py:81  kj = torch.arange(int(en.max()), device=device)
```

`int(en.max())` is a **host read of a tensor's contents, used to size another
tensor**. Inside `torch.xpu.graph`, operations are *recorded, not executed*, so
the tensor `en` holds whatever was in that memory and the read returns garbage.
The garbage became an `arange` length, and the allocator was asked for a
petabyte.

## The audit that should have come first

Grepping the decoder's whole call graph for host reads finds **exactly one
pattern**, in two places:

| File | Line |
| --- | --- |
| `scripts/ltx_na_axis_candidate.py` | 81: `torch.arange(int(en.max()), device=device)` |
| `comfy_kitchen/backends/eager/na.py` | 76: the same expression |

Everything else is benign: `int(dim * mlp_ratio)` is Python arithmetic at module
construction, and the `.float()` calls are dtype casts.

The transformer blocks were audited this way before packet14 and the single
`.item()` in `av_model.py:723` was confirmed to sit outside the block. **The
decoder was not audited, and that is the process failure here**, not the adapter.

## The fix is small and exact

In the lane's own candidate, `ends` is already a **Python tuple** -- it is used
as part of the cache key on the line above. So `int(en.max())` is a pointless
device round trip: `max(ends)` returns the identical integer on the host, with no
tensor read at all. That is bit-identical by construction and also removes a
device synchronisation from the ordinary eager path.

Two things remain unresolved and must be settled before capture is retried:

1. whether the upstream `comfy_kitchen` copy at `eager/na.py:76` is still
   reachable from the axis-cache path (its comment says oversized axes fall back
   to the original uncached operations); it lives outside the sealed tree;
2. whether the axis cache is warm by capture time. When `axis_cache` has the
   entry, line 81 is skipped entirely, so the eager reference and warm-up calls
   the adapter already performs may be enough on their own.

## Incident: a GPU engine reset, caused by this experiment

Aborting the capture left the device faulted. The kernel recorded, on
`0000:23:00.0`:

```
xe ... GT0: Fault response: Unsuccessful -ENOENT     (x2)
xe ... GT0: Engine memory CAT error [18]: class=bcs, logical_mask: 0x1, guc_id=6
xe ... GT0: Engine reset: engine_class=ccs, logical_mask: 0x1, guc_id=2
xe ... GT0: Fault response: Unsuccessful -EINVAL
```

The driver reset the engine and the host stayed up: all four render devices are
present, no process owns them, load and memory are normal, and there was no hard
lockup. The server process itself died on the fatal error.

**Unlike [the earlier lockups](xe-lockup-incident-01.md), this fault is
attributable to this experiment.** The distinction matters: those were a
spontaneous `xe` GuC hard lockup in the idle task; this is a driver-visible
consequence of asking for an impossible allocation and abandoning a capture
part-way through.

Consequence: the sealed launcher's preflight greps the **whole boot** journal for
`Fault response|CAT error|engine reset`, so it will refuse every launch on boot
`831530c8` by design. GPU work on this lane resumes on a fresh boot; the lane's
`docs/local-ops.md` same-boot recovery path exists but is bound to a different
historical incident and is not reused here.

## Standing result is unaffected

The qualified position remains packet21's: warm clip **4.682 s** against a
6.415 s control, sampler **1.942 s** at 1.86x, decode **0.560 s**, everything
bytewise exact. Nothing in this note changes it.

Evidence: [`data/vae-capture-incident-01/`](../data/vae-capture-incident-01/)
holds the kernel fault extract, the execution error and the five clips that did
complete.
