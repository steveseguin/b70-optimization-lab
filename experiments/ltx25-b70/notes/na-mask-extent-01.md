# Remove a redundant decoder mask scalar readback

2026-09-14. This is an inactive exact-output generation candidate. No live
runtime file, model parameter, attention algorithm, sampler step, precision or
resolution changes have been deployed. The previous goal turn made concrete
progress by committing the bounded comparison client and saved-evidence checks
as `27362ce64`. This turn returns to decoder execution overhead.

The pinned Comfy Kitchen eager neighborhood-attention helper builds an integer
tensor `en` from the Python tuple `ends`, computes `en.max()` on the device,
then converts the scalar to a Python integer to size `arange`. The candidate
uses the already available Python bounds instead:

```diff
-        kj = torch.arange(int(en.max()), device=device)
+        kj = torch.arange(max(ends), device=device)
```

This removes three device reductions and scalar readbacks per geometry group,
one for each axis. It retains `en` construction, `arange` dtype/device, mask
comparisons, mask allocation/fill, query/key/value operations, tile grouping,
and every SDPA argument. This is local reuse of geometry metadata, unrelated
to prompt caching or reuse of generated video.

The sole `_group_mask` caller is `na3d`. Its relative starts/ends are nonempty
tuples of Python integers derived from `_window_bounds` and nonempty tiles.
For representable signed-int64 values, reduction after tensor construction
and Python `max` return the same integer extent. Empty/floating-point direct
helper calls are outside this caller contract and are not claimed compatible.
An independent source review confirmed the caller/type boundary and unchanged
downstream operations. Public custom-op fake shape inference does not execute
this helper.

Source provenance: Comfy Org's Apache-2.0 implementation at
`/home/steve/.venvs/ltx25-baseline/lib/python3.12/site-packages/comfy_kitchen/backends/eager/na.py`.
Original SHA256:
`4f1d82fe02af995d395969667f6cfd8d10635c3144eec8ca78fe37c103803995`.
Candidate SHA256:
`4df083f73ee533e6a45efd9f7cc14e0a2abf21bbc065c128b19ff5083be6f228`.
Original/candidate sources, exact patch and source receipt are preserved under
`data/na-mask-extent-01/`; the reusable patch is also in
`patches/remove-na-mask-extent-readback-01.patch`.

Preparation and standard-library validation:

```text
python3 -B -S experiments/ltx25-b70/scripts/prepare-na-mask-extent.py --output experiments/ltx25-b70/data/na-mask-extent-01
```

The preparer checks that the complete source AST changes only at the declared
extent expression. It extracts only the original integer geometry functions,
without Torch imports or custom-op setup. All17,728 nonempty axis subranges
across144 causal/noncausal configurations preserved the extent after independent
signed-int64 serialization/reduction. Cases include singleton axes, larger
kernels than dimensions, even kernels, boundary windows and partial tiles.

The original geometry code was also evaluated on source-derived default
untiled decoder stages for a `[4,8,8]` latent. This gives the following
**conditional source counts**, not a runtime trace or performance measurement:

| Stage dimensions | Blocks | Geometry groups per block | Removed scalar reads per block |
| --- | ---: | ---: | ---: |
| 6x8x8 | 4 | 1 | 3 |
| 6x16x16 | 6 | 1 | 3 |
| 11x16x16 | 4 | 1 | 3 |
| 21x32x32 | 2 | 8 | 24 |
| 25x64x64 | 8 | 18 | 54 |

The resulting total is522 calls if the actual invocation follows that full
untiled default path. The dimensions account for the two padded latent frames,
causal leading-frame removal during temporal upsampling, and the trailing
context crop. Actual VAE tiling may change the count. No new shape trace was
collected; this count must not be promoted as an observed count.

Why try it: the preserved nonblocking Python stack profile contains32 samples
at `_group_mask`, including the scalar-readback line. This establishes that
the path executed, not its contribution to GPU or end-to-end time. The prior
`resident-split-03` node-event profile assigns approximately0.608s to VAEDecode,
but node intervals are approximate client events and include queued work.
Neither profile estimates the speedup from this patch.

Outcome: exact integer/source checks pass; native mask parity, attention parity,
full four-output parity and repeated generation are pending. No speed result
exists. The existing compiler candidate remains pending separately; this patch
does not replace its evidence or combine changes into an unidentifiable run.

Next qualification: use the separate small native mask/attention gate after
host recovery and health checks, then a separately pinned runtime packet and
full-clip original-reference/repeat gates before matched timing. A failed gate
must halt requests and preserve the failure; no restart or fallback loop.
The current fault latch must prevent native testing, including nominal CPU
Torch tests, because the earlier tiny CPU import/test remains kernel-stalled.
No reboot, server action, GPU request or host-setting change occurred this turn.
