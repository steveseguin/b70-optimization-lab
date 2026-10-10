# Packet 132 memory evidence: the last 145-frame admission gap

This is a CPU-only audit of saved files. No GPU import, live request, launch,
unit operation, existing-run write or scratch directory was used. Exact source
paths and SHA256s are in the [compact evidence](../data/resume-20261008/continuation132-memory-evidence.json).
GiB means 2^30 bytes. Static placement savings below are projections, not a
measurement that those bytes became physically free.

## What packet 131 released

The refusal at `stream131-qgraph-c000000` contains the complete allocator
release receipt inside both `stream-halt.json` and its decode-failure record.

| xpu:3 quantity | Before | After | Change |
|---|---:|---:|---:|
| Physically free | 15,825,240,064 B | 15,825,240,064 B | 0 |
| Allocated | 15,219,862,016 B | 15,219,862,016 B | 0 |
| Reserved | 17,028,874,240 B | 17,028,874,240 B | 0 |
| Reserved minus allocated | 1,809,012,224 B | 1,809,012,224 B | 0 |

Thus the release recovered **zero bytes on xpu:3**. It took 0.016944877 s.
The remaining reserved-unused upper bound is **1.684773922 GiB**, not promised
reclaimable memory. Card 0 reservation fell 52,428,800 B; card 1 fell
106,954,752 B; card 2 did not change. These sequential samples are net
observations, not isolated causality measurements. Repeating `empty_cache`
without changing tensor/pool lifetimes has no demonstrated benefit.

The actual arithmetic is:

`5,368,709,120 + 9,663,676,416 + 805,306,368 = 15,837,691,904 B required`.

`15,825,240,064 - 15,837,691,904 = -12,451,840 B = -0.011596680 GiB`.

This deficit **already includes the complete 0.75 GiB screening band**.
Without the band the margin is 792,854,528 B = 0.738403320 GiB. The requested
0.4–0.6 GiB improvement is a useful extra margin target, not an additional
0.75 GiB deficit. Keep both the 9 GiB floor and 0.75 GiB band unchanged.

## Capture evidence and the proposed allowance

The 121-frame packet 119 and 120 freezes each contain one captured method,
`forward_pre_diffusion`, with input [1,128,16,8,8] and BF16 output
[1,121,64,64,256]. Neither captured `forward_diff_step`. In 119, allocated
15,220,386,304 → 16,271,590,400 B and reserved
17,028,874,240 → 20,459,814,912 B. In 120, allocated
15,466,932,736 → 16,518,136,832 B and reserved
17,217,617,920 → 20,648,558,592 B. Both therefore show allocated growth
1,051,204,096 B and reserved growth **3,430,940,672 B = 3.1953125 GiB**.
These counters include warm-up/proof allocation and pool reservation. They
are neither an isolated capture peak nor a permanent-pool-only measurement.

The proposed temporal-squared rule gives
`3,430,940,672 × (19/16)^2 = 4,838,162,432 B = 4.505889893 GiB`.
The inherited 5 GiB reserve exceeds that estimate by
**530,546,688 B = 0.494110107 GiB**. Rounding the estimate up to 4.51 and
adding 0.25 gives 4.76 GiB, 0.254110107 GiB above the unrounded estimate.
Using conservative integer ceiling, that is **5,111,011,083 B**; it reduces
the admission allowance by **257,698,037 B ≈ 0.24 GiB**. It releases no
physical memory. The new required free is 15,579,993,867 B; the saved free
would exceed it by **245,246,197 B = 0.228403320 GiB**, including the band.

The two 121 runs reproduce the starting measurement. They do **not** prove
the quadratic growth law, its margin, or a 145-frame memory upper bound.
Therefore packet 132 recognizes `scaled-476` but **fails it closed** pending
a measured 145-frame bound. It is not an admitted lower-reserve launch arm
or a `measured145` claim. Future qualification must retain fresh physical admission,
measured capture growth refusal above its allowance, postcapture 9.75 GiB
free, full native references and sustained memory checks. A postcapture
check cannot make the allowance a hard allocation cap. If policy requires
a measured 145-frame bound before tightening, do not enable this option:
audio-only with the inherited 5 GiB allowance already clears this saved
admission. A future successful 145 capture can establish the needed bound.

## Remedies ranked for this refusal

1. **Audio VAE and vocoder only, xpu:3 → xpu:2:** exact checkpoint inventory
   364,666,868 B = **0.339622486 GiB** (VAE 106,496,804; vocoder 258,170,064).
   Sealed131 `launch/serve-encoder.py` passes `--bf16-vae`; the native dtype
   selector gives that flag priority over the audio class working-dtype list.
   The move preserves native BF16. The upsampler remains on xpu:0. Projected first-capture screen margin with
   the original reserve is **352,215,028 B = 0.328025807 GiB**. Combined with
   the optional 4.76 allowance it is **609,913,065 B = 0.568025806 GiB**.
   Preserve runtime/dtype and compare the CPU waveform bytes, shape, dtype,
   sample rate and latent identity against the xpu:3 native decode. Compare
   the three eager controls on both cards before graph capture, unload the
   reference weights to CPU, and retain all nine whole-chain waveform checks
   and repeat/fresh identity requirements. Refuse any byte mismatch. Never
   infer audio exactness from video or latent equality.
   Check card 2 workspace, its existing floor and screening at every required
   boundary. Its display and audio must remain serial for this first option.
2. **Video encoder only, xpu:3 → xpu:2:** inventory 637,873,794 B =
   **0.594066264 GiB**, projected original-reserve margin 0.582469584 GiB.
   Its users can potentially keep their decode-thread schedule, but this is a
   split VAE, not a VAE-device-string edit. The shared native VAE patcher and
   `sd.py` loading/device/memory checks currently cover both encoder and
   decoder, and precompute guards synchronize and inspect xpu:3. Splitting
   requires separate encoder placement and both-card guards, unchanged cache
   checks, native binding pins, and an xpu:3 same-input encode byte oracle.
   With audio already sufficient, defer this larger unqualified change.
3. **Blocked measured121-derived 4.76 allowance:** **0 GiB physically freed**,
   **0.24 GiB lower budget**; estimated reserve-only screen margin
   0.228403320 GiB. Evidence and limitation are above. Safe first recommendation
   is audio plus parent reserve; the combined arithmetic is hypothetical and
   the lower-reserve selector fails closed pending measured145 evidence.
4. **More allocator release:** **0 GiB verified or guaranteed** beyond the
   existing attempt; 1.684773922 GiB remains reserved-unused. Future investigation
   must identify dead tensors or allocator segments that can actually be
   released without touching live graphs, native references, or checks. Do not
   count the entire unused envelope, add a release loop, or reset the device.

## Encoder copy accounting

The sealed `resolution/components/precompute_guard.py` and `integration.py`
require CPU float32 anchor pixels and CPU float32 encoded results. Stage A
resizes to 128×128; B uses 256×256. `source/comfy/sd.py:1418` converts pixels
to BF16 before the native encoder's chunked upload. The single-frame BF16
uploads are **98,304 B (A)** and **393,216 B (B)**. The BF16 normalized
results are **4,096 B** and **16,384 B** before CPU float32 expansion to
8,192 and 32,768 B. Correctly routing this existing CPU→encoder→CPU path
moves those transfers to card 2: **zero extra full-frame inter-card bytes**.
If an implementation leaves normalization on card 3, transferring means back
adds **20,480 B/chunk** (twice that if needlessly copying means and logvar).
The normalizer's `.to(x)` permits normalization on card 2 with two 128-element
BF16 statistics vectors: 512 B per encode, 1,024 B for A+B, unless resident.
This is source-derived byte accounting, not a latency measurement or exactness
pass. Preserve the arithmetic order and test actual result bytes.

## Isolated audio timing and projected cadence

Do not attribute packet 123's bundled slowdown to audio: it also moved the
0.927351 GiB upsampler. A future authorized matched campaign should keep 145
frames, display replica2/serial, sampler split20/28, all snapshot/storage/GC
settings, seeds, qualification and prompts fixed. Compare audio legacy vs
xpu2 only with dg0 first so the parent refusal does not confound the result;
use at least two fresh servers per arm under the owner's launch authority.
Then qualify the graph plus audio arm. Time audio decode with both start and
end, transfer boundaries, card synchronizations, and waveform verification
separately. Retain natural end-to-end chunk periods, parity medians, p90,
all four-card memory samples and fixed qualification bytes. No repeated
server work is authorized by this CPU preparation.

At 145 the BF16 audio latent is 1×8×151×16 = 38,656 B; the CPU float32
waveform is 1×2×288,480 = 2,307,840 B. Moving the audio destination replaces
its existing transfer target; any additional oracle transfer is qualification
cost and must be reported separately. Preserve exact waveform checks.

The inherited conditional cone forecast is **5.25–5.35 s per 6 s of video
= 0.875–0.892 s/s, plus the unmeasured isolated audio placement cost**.
It is not a packet 132 speed measurement. Native cross-card audio exactness,
actual freed memory, the 145 capture peak, later qualification references,
steady-state fit and repeated cadence remain unclosed by this CPU audit.
