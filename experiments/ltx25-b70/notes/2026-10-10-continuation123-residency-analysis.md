# Packet 123: move two auxiliary owners, keep sampler and video arithmetic

The smallest useful change among the complete, independently owned components
is **upsampler xpu:0 → xpu:2 plus audio VAE/vocoder xpu:3 → xpu:2**. The option is
`LTX_AUX_RESIDENCY=legacy|xpu2`, default `legacy`. Both moves are required:
upsampler alone leaves the xpu:3 shortfall; audio alone leaves xpu:0 short.
This is a planning admission, not a measured memory or output claim. Qualify it
at 145 frames before the coordinator considers 169. The static-credit 169
xpu:3 lower estimate is only **0.825 GiB above its unchanged floor**, leaving
0.075 GiB beyond the required 0.75 GiB allowance. Retained allocator storage can
invalidate a weight-only projection; actual phase readings decide admission.

[Analysis script](../data/resume-20261008/continuation123-residency-analysis.py)
and [JSON output](../data/resume-20261008/continuation123-residency-analysis.json)
use Python's standard library, five safetensors headers, the 145 preparation and
component receipts, and the frozen [122 evidence](../data/resume-20261008/continuation122-evidence.json).
The model payloads were never read or loaded. Header-with-length hashes and
receipt hashes bind these inputs; a header hash is explicitly not a full model
payload hash. All memory below is GiB (2^30 bytes).

## Resident inventory

`two-way20-28` is the sampler split: blocks **0–19 on xpu:0**, blocks **20–47 on
xpu:1**. It is not the text split. Text remains layers **0–23 on xpu:2** and
**24–47 on xpu:3**. Thus moving “the text encoder from xpu:0” would have no
effect: it is not there. xpu:2 has 9.706 GiB above its floor in the measured 145
dg0 line **without** a display replica; do not describe that as room with the
replica already included.

| Resident owner | Device | Bytes | GiB | Evidence |
|---|---|---:|---:|---|
| Sampler 20 blocks plus non-block state | xpu:0 | 20,354,297,920 | 18.956417 | Preload tensor census minus upsampler |
| Sampler 28 blocks | xpu:1 | 21,653,793,280 | 20.166667 | Preload census and converted header agree |
| Upsampler | xpu:0 | 995,735,808 | 0.927351 | All 72 tensors BF16 in header |
| Text primary, including embedding/projections/other registered state | xpu:2 | 15,330,870,852 | 14.277986 | Component receipt parameter and buffer records |
| Text layers 24–47 | xpu:3 | 10,900,713,520 | 10.152081 | Same records, layer ownership split |
| Video encoder | xpu:3 | 637,873,794 | 0.594066 | BF16 header |
| Video decoder | xpu:3 | 834,267,488 | 0.776972 | BF16 header |
| Video channel statistics | xpu:3 | 512 | 0.000000477 | BF16 header |
| Audio VAE | xpu:3 | 106,496,804 | 0.099183 | BF16 header |
| Audio vocoder | xpu:3 | 258,170,064 | 0.240440 | BF16 header |

The sampler checkpoint includes F32 scale tables which the unchanged native
loader already converts to BF16. Each runtime block is **773,349,760 bytes =
0.720238 GiB**, not the checkpoint's 773,546,368 bytes. Non-block sampler state
is 4,887,262,720 bytes; xpu:0 adds the known 40,000-byte constructor sigma
buffer. The audio and video headers are entirely BF16, so their static credit
does not assume a new precision change. Combined VAE runtime inventory is
1,836,874,030 bytes, 65,368 bytes above the two checkpoint payloads. That small
constructor-owned difference cannot be assigned to one VAE from these receipts;
the move credits only the audio checkpoint's smaller exact 364,666,868 bytes.

Preparation already has all **480 text graphs across 48 layers** captured,
but zero sampler routes. Text graph pools are shared per device/thread;
individual routes own their static argument/output buffers. Text is stateless
prefill (no layer KV cache). The accepted prompt reuse and small staged argument
caches are inherited; no new prompt, latent, response, or decoder reuse is
introduced. Sampler captures later use shared per-device/thread pools and
per-route static tensors for stage A/B. dg0 has **zero video decoder graphs**,
no decoder graph-pool growth, and no display replica. The encoder's causal
cache census records zero entries before/after the single-image anchor encode.

| Preparation allocation accounting | xpu:0 | xpu:1 | xpu:2 | xpu:3 |
|---|---:|---:|---:|---:|
| Exact tensor inventory | 19.883768 | 20.166667 | 14.277986 | 11.862803 |
| Allocated beyond that inventory | 0.000058 | 0.000070 | 2.274610 | 2.771027 |
| Allocator reservation | 20.433594 | 20.824219 | 18.861328 | 16.226562 |

The residuals on text cards include graph/static/workspace allocations; they
are not separately metered text graph-pool sizes. Receipts do not expose an
exact byte decomposition of every graph pool, static buffer and cached tensor.
Claiming one by subtracting cumulative peaks would be false. The aggregate is
preserved in the planning envelope and the missing component measurements are
an explicit open item.

## Per-phase storage, including retained allocations

| Minimum sampled physical free at 145 | xpu:0 | xpu:1 | xpu:2 | xpu:3 |
|---|---:|---:|---:|---:|
| Prepared, before sampler capture | 10.965 | 10.574 | 11.837 | 14.853 |
| Request before | 9.423 | 9.828 | 11.837 | 10.850 |
| A conditioning | 9.454 | 9.848 | 11.837 | 14.664 |
| B conditioning | 9.270 | 9.848 | 11.706 | 10.859 |
| Request after | 9.302 | 9.828 | 11.706 | 10.850 |
| Greatest recorded allocated peak | 20.559 | 20.764 | 18.073 | 16.657 |
| Greatest sampled allocator reservation | 21.256 | 21.326 | 19.000 | 19.752 |

Before-cone minimum free on xpu:3 is 14.533 GiB. Its later 10.850 GiB minimum
includes display/encode/audio overlap and reservation tails. The 4.003 GiB
preparation-to-minimum loss on that card must remain in the estimate; moving
audio weights does not prove that all related reserved workspace disappears.
The upsampler is 0.046 s median inside B preparation; its isolated peak and the
isolated audio peak are not available. A/B anchors remain single images.

169 uses 22 latent frames versus 19 at 145. As in packet 122, scale the complete
preparation-to-minimum loss between 22/19 and its square, while leaving static
weights unscaled. These are engineering ranges, not proven upper bounds.

## Alternatives and the selected move

| Change | Static freed on source | Destination cost | 169 verdict, before new workspaces |
|---|---|---|---|
| Sampler 18/30 | xpu:0 +1.440 | xpu:1 −1.440 | xpu:1 only 0.134–0.270; xpu:3 still 0.486–1.218: fails |
| Sampler 16/32 | xpu:0 +2.881 | xpu:1 −2.881 | xpu:1 −1.307 to −1.170: fails |
| Upsampler only →2 | xpu:0 +0.927 | xpu:2 −0.927 | xpu:3 still fails lower scenario |
| Audio owner only →2 | xpu:3 +0.340 | xpu:2 −0.340 | xpu:0 still 0.693–1.003: fails |
| **Upsampler + audio →2** | **xpu:0 +0.927, xpu:3 +0.340** | **xpu:2 −1.267** | **Every static-credit lower estimate ≥0.75** |
| Upsampler + video encoder →2 | xpu:0 +0.927, xpu:3 +0.594 | xpu:2 −1.521 | Fits static estimate; requires new split VAE owner and encode guards |
| Upsampler + text layer24 →2 | xpu:0 +0.927, xpu:3 +0.418 | xpu:2 −1.345 plus text graph/static state | Fits static estimate; requires new text split/graph identity |

Both sampler alternatives are outside the current named placement grammar
(`two-way` and `two-way20-28`) and would need new qualification identities and
source guards. Neither solves xpu:3, so they are closed for this packet.
Moving all text-secondary weights to xpu:2 costs 10.152 GiB before its graph
state, already larger than the 9.706 GiB margin; this is not admissible.
Moving stage-B execution alone without splitting its encoder owner would add
a replica instead of freeing weights. Moving that encoder is possible, but
touches video VAE binding, native encode device routing, causal cache ownership,
and B-overlap guards. The audio owner is both smaller and independent.

The selected implementation changes the native audio VAE constructor target
and the unloaded CPU upsampler patcher's target. It never migrates live models.
The upsampler gate checks zero loaded bytes, non-dynamic ownership, every
parameter/buffer still on CPU in BF16, and exactly 995,735,808 bytes before
changing its target. No numerical operator is replaced. All model components
continue to be fully resident. Native and candidate role checks import the
new fixed role mapping; their floors and tensor/ownership checks remain.
The opt-in runtime also synchronizes and samples xpu:2 immediately before and
after each auxiliary operation: at least **4.75 GiB free before** (2 GiB floor,
2 GiB workspace allowance, 0.75 GiB screening margin) and **2.75 GiB after**.
The upsampler receipt preserves both samples. These are admission/boundary
checks; they do not falsely call a shared cumulative allocator counter an
isolated workspace peak. The legacy helper path makes no device calls.
The disabled option follows the old placement. A new runtime/qualification
identity must bind the option, and three-chain and per-chunk byte checks remain
required; identical hardware alone does not establish output equivalence.

The native upsampler already takes a CPU intermediate and returns to CPU.
At 169 these F32 tensors are 180,224 input bytes and 720,896 output bytes.
Audio likewise takes a 90,112-byte F32 CPU latent and returns a 2,691,840-byte
F32 waveform. The selected destinations therefore add **zero additional
direct peer-to-peer hops**, changing the endpoints of existing transfers.
The video's channel-statistic buffers already cross from xpu:3 to the
upsampler target: four 256-byte BF16 transfers per normalize/un-normalize pair
(1,024 bytes total), now to xpu:2 instead of xpu:0.
Even pessimistically counting all 3,683,072 bytes as an extra transfer costs
0.00037–0.00368 s at an assumed 10–1 GB/s; this is arithmetic, not a bandwidth
measurement, and excludes dispatch/contention. Allow about 0–0.10 s cadence
change for scheduling uncertainty. A text split still has one boundary hop;
changing the boundary does not remove it. A VAE split would add device routing
and guard work even though single-frame pixel inputs are small.

## Proposed order and ranges; no launches performed

Margins below are above the unchanged 8/8/2/9 GiB card floors, in xpu:0/1/2/3
order. The selected pair reserves an additional **2 GiB** on xpu:2 for newly
colocated upsampler/audio workspaces, without crediting any removed workspace
on xpu:0 or xpu:3. This is an explicit conservative planning allowance, not a
measured maximum; actual workspace and overlap readings must still qualify.

1. **145 dg0, display3, legacy residency, race fix:** predicted repeat band
   **5.45–6.10 s / 6.0 s = 0.908–1.017 s/s**. Reference measured margins
   **1.270 / 1.828 / 9.706 / 1.850 GiB**. This checks the race fix with existing
   placement and supplies a current same-length comparison.
2. **145 dg0, display3, xpu2 auxiliary residency:** predicted **5.45–6.20 s =
   0.908–1.033 s/s**. Planning margins **2.198 / 1.828 / 6.439 / 2.189 GiB**,
   including the extra destination workspace allowance. Require same-length
   byte equality against legacy plus the three-chain gate, phase memory and
   retained reservation observations before increasing length.
3. **169 dg0, display3, xpu2 auxiliary residency:** predicted **5.95–6.65 s /
   7.0 s = 0.850–0.950 s/s**, central about 6.2 s (0.886 s/s). Planning margins
   **1.620–1.930 / 1.574–1.711 / 6.439 / 0.825–1.557 GiB**. No same-length 169
   legacy run is proposed because its memory estimate fails. Three-chain
   identity, actual geometry, per-chunk byte checks and phase floors decide
   whether this candidate can be used. The xpu:3 lower estimate is fragile.

The underlying measured 97/121/145 sampler A medians are 1.685/1.786/1.905 s;
B medians 1.201/1.387/1.677 s (mixed sessions). Descriptive fits give 169 A
2.013 s and B 1.897 s; planning bands are A 1.95–2.15 and B 1.85–2.05 s. Eager
cone uses 0.85–1.10 s because its fixed last-frame dependency and tiling make
the observations non-monotonic. Remaining chain cost is about 1.10–1.30 s.
Do not add nested snapshots/conditioning buckets twice. These components
support the period forecast; none is a measured 169 point.

**169 display does not yet have a proven 3 s execution time.** The measured
145 median is 2.719 s; straightforward frame scaling predicts **3.170 s**.
Because 121 and 145 eager medians barely changed, use a broad **2.72–3.30 s**
planning range. Do not assert that audio relocation makes the video decoder
itself faster. The inherited **`GO_BOUND_S=3.0` bounds waiting for the next
sampler to start, not the subsequent display decode's execution time**.
`stream_schedule_gate.py` checks the combined sampler-A/sampler-B release waits
against three seconds; it imposes no three-second decode timeout. Both existing
wait bounds remain unchanged. Therefore a 3.17 s display forecast does not by
itself violate that code contract or establish that a replica is needed. It
does leave the user's requested ≤3 s display target unproven. The run must
report actual decode duration, queueing and cadence; if ≤3 s is a separate hard
acceptance gate, it must pass before that performance claim is made.

The xpu:2 display replica is a separate fallback research arm, **not yet a
recommended launch**. Its 169 transient projection is **4.101–5.639 GiB**, so
6.5 GiB is the prior planned allowance. Using the measured replica before-decode
free base (already including replica weights) and subtracting the new 1.267 GiB
auxiliary weights leaves **0.943 GiB** above the xpu:2 floor after that allowance.
That is before auxiliary workspace: applying the 2 GiB allowance gives
**−1.057 GiB**. A replica therefore needs measured non-overlap or tighter peak
accounting before admission; it also cannot promise the same decoder completes
in <3 s on another identical card. **145 dg1 replica remains inadmissible**.

Open work is exactly the device-dependent evidence: physical-free benefit and
allocator tails of the move; isolated/newly colocated workspace peaks; exact
full-model cross-device audio/upsampler output at 145; every 169 memory, timing
and byte check; the 3 s display bound; and any replica overlap measurement.
No device API, server request, launcher, live preflight, systemd operation,
process signal, `/dev/dri` access, existing-run write or live-client write was
used to produce this analysis.
