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

## Update, September15: three more blockers, each caught by a guard

The host read was removed (`int(en.max())` -> `max(ends)`, **288/288 geometries
bitwise equal** on CPU) and capture was retried. It failed three more times, and
every failure was caught by a guard rather than producing wrong pixels:

| Packet | Refusal | Cause |
| --- | --- | --- |
| 23 | `Node 'LTXNAAxisDecode' not found` | `CANDIDATE_SHA` is pinned as a literal in the router and the decode node. Changing the candidate made their import fail, so the node **silently never registered** |
| 24 | `NA router source differs` | the node also pins `ROUTER_SHA`, invalidated by repointing the router. The chain is candidate -> router -> node |
| 25 | `captured an inert graph; replay ignored its input` | the decoder is on xpu:3 while the current device is xpu:0. Setting only the capture *stream* is not enough; `torch.xpu.graph` synchronises and empty-caches the **current** device and records nothing |
| 26 | `graph replay differs from eager execution` | the real blocker, below |

The pinned-digest chain is the [sealed-literal](../../../docs/local-ops.md) trap:
a stale pin fails *silently*, because ComfyUI catches the import error and simply
omits the node. `/object_info/<name>` returns **200 with an empty body** for an
unregistered node, so the obvious health check proves nothing unless it asserts
the body actually contains the class. The preparer and checker now verify that
every `*_SHA` pin in the NA chain names the file the packet actually ships.

## The real blocker: host-to-device copies cannot be captured

An isolated probe settles it:

| Case | Replay matches eager | Stable |
| --- | --- | --- |
| A: `torch.tensor(host_list, device=...)` inside capture | **no** | no |
| B: the same values already device-resident | yes | yes |
| C: mutating the host list afterwards **changes replay output** | — | — |

Case C is the proof: the captured graph holds a **pointer to host memory**, not a
copy of the values. After capture that buffer is freed and reused, so replay
reads whatever now occupies it.

`_group_mask` builds its masks with `torch.tensor(starts, device=device)` and
`torch.tensor(ends, device=device)` on **every call**, because `na3d` creates its
`axis_cache` fresh per invocation (`axis_cache = {}`). So every capture of the
decoder records dangling host pointers, and replay silently diverges. The
bitwise proof caught it; without that proof this would have shipped visibly
wrong video.

**The fix path is clear but is its own change:** give the axis cache a lifetime
longer than one invocation, keyed by geometry and device and bounded as it
already is (64 entries, 4096 elements). The eager reference and warm-up calls the
adapter already performs would then populate it, and the captured call would find
the masks **already device-resident** -- case B, which captures correctly. That
converts the decoder into a valid capture target without touching its arithmetic.

This is not attempted here. The decoder is 0.560 s of a 4.682 s clip, so the
whole prize is roughly 0.2 s, and the larger measured lever is elsewhere.

**No GPU fault occurred in any of these four attempts** -- the capture teardown
added after the first incident holds, and the kernel fault count for the boot
stayed at zero throughout.

Evidence: [`data/vae-capture-incident-01/`](../data/vae-capture-incident-01/)
holds the kernel fault extract, the execution error and the clips that completed;
[`data/h2d-copy-under-capture-01.json`](../data/h2d-copy-under-capture-01.json)
holds the host-to-device probe.


## Second attempt, September15: the host read is gone, a new blocker is not

The host read was removed and the geometry cache given a lifetime longer than one
call, so the masks are device-resident when capture happens. Both changes are
proven bitwise equivalent on CPU: **288 cold-path comparisons and 48 cache-hit
comparisons**, with the cache bounded at 22 entries of at most 4096 elements.

Two implementation details were forced by the lane's own design and are worth
recording:

- The router **sandboxes** the candidate: it extracts the four function
  definitions by AST and execs them in a namespace holding only `torch`, `math`
  and two pinned budget constants. A module-level cache cannot survive that, so
  the cache is a **keyword-only default argument** whose mutable default persists
  across calls.
- Changing the candidate invalidates `CANDIDATE_SHA` in the router and the decode
  node, and changing the router then invalidates `ROUTER_SHA` in the node. The
  chain is candidate -> router -> node and has to be repointed in that order. The
  preparer now refuses to seal a packet whose pins do not name the shipped files,
  which is what caught it.

With those fixed the decoder no longer dies on the allocation, and the
transformer arm still runs exact at 1.969 s. But capture now fails a different
gate: **`forward_pre_diffusion captured an inert graph; replay ignored its
input`**, with **zero** "XPU Graph is empty" warnings from the driver. So the
graph has recorded content, yet perturbing its static input does not change the
replayed output. That is not the empty-capture failure fixed in packet26 by
setting the device context, which is present and verified in the shipped file.

Leading untested hypothesis: `forward_pre_diffusion` ends in a slice
(`x = x[:, :-(n * temporal_upscale)]` when trailing padding is applied), so the
returned tensor may be a view whose storage is not the one replay writes. That
would make the output stale while the graph itself is live. Confirming it needs
one more diagnostic cycle.

**Status: still blocked, and deliberately parked.** The whole prize is about
0.2 s on a 4.68 s clip, and three cycles have gone into it. The guard behaved
correctly every time -- it refused rather than shipping wrong pixels, which is
the only reason this is a schedule cost rather than a silent quality regression.
The persistent-cache and host-read changes are committed and proven, so a future
attempt starts from there rather than from scratch.
