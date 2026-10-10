# Packet 120: separate the display decoder, preserve the anchor path

CPU preparation only. Parent 119 manifest:
`d4b99d333f8193fc74041290b3cc3ebc7309b73836323997d14271a9aa246890`.
The coordinator owns the running LTX service. No GPU, device, model request,
launch, launch preflight, systemd operation, signal, live-directory write or
host-setting change belongs to this task.

The [119 receipt analysis](2026-10-10-continuation119-results-121.md) corrects the
initial attribution. Packet 119 was slower than 118b dg0. Its cone was faster,
but near-floor safety checks ran both the fingerprint and the full walk on
almost every B-before, B-after and request-after snapshot. The native upsampler
itself was about 0.032 seconds in both configurations. It resides on xpu:0;
condition B and the native VAE reside on xpu:3. Receipt timestamps describe
host calls and completed results, not a hardware queue trace.

## A. A decoder-only display instance on xpu:2

`LTX_DISPLAY_DEVICE=xpu:3|xpu:2`, default **xpu:3**. Off preserves 119's decode
path and scheduling. The optional xpu:2 path is restricted to 121 frames,
frame anchors, cone anchors and `eager-display`. The existing cone stays on
xpu:3. No encoder moves, no precision changes, no graph is captured on xpu:2,
and the admitted sampler, text and upsampler objects keep their placement.

Copy the native decoder and channel statistics before installing graph/cone
wrappers. Copy each tensor directly to the destination and check its bytes;
exclude the encoder explicitly. Retain the native first-stage decode, its
seed-zero noise generation, BF16 weights/latents, FP32 CPU output, copy,
normalization and reshape order. The replica has independent tensor storage.
It does not enter the model manager and therefore cannot request an eviction
of another admitted model. Residency and physical-free-memory checks guard it.

Same model and same operation order are an exactness argument, not proof that
the two cards choose identical numerical kernels or random-number results.
CPU tests cannot close that question. Therefore the option ships off by default
and the full-model cross-card byte gate is mandatory:

- On **all nine chunks**, including eager, graph and repeat chains, compare the
  entire xpu:2 display tensor with an xpu:3 **uncached eager** decode of the same
  latent. Require identical shape, dtype and bytes. Eager control output stays
  on xpu:3; its additional replica result is a separate comparison.
- Keep the original cross-chain latent, images, waveform and anchor checks.
- On every live cone chunk, the display's last frame must equal the xpu:3 cone
  anchor byte for byte. Any mismatch halts/latches; no automatic fallback.
- Bind display device, residency facts and comparison hashes into receipts,
  qualification and client expectations. Missing proof is a failure.

One ordered decode thread remains. It runs cone, anchor handoff, existing
encode preparation and display in the inherited order. Moving the work to
another device does not require a second thread because the prompt thread
already overlaps the decode thread. A second decode thread would introduce
new lifetime, admission and queue races without evidence of a gain.

## Residency census and admission

The checkpoint header contains 834,267,488 decoder bytes and 512 channel-statistic
bytes, versus 637,873,794 encoder bytes that are **not copied**. The runtime
recounts the actual resident tensor bytes; checkpoint storage is not an allocator
measurement. The inherited graph pool remains on xpu:3; replica graph pool is zero.

The saved preparation reading has **12,709,556,224 bytes free on xpu:2**,
17,773,215,232 allocated and 20,252,196,864 reserved. Thus “12.5 GB used” is not
the recorded reading. Only 10,562,072,576 bytes are available above the 2 GiB
floor. With roughly 0.834 GB copied weights and a 4 GiB transient allowance,
about 5.43 GB remain above that allowance plus floor on this saved reading.
This is an estimate from saved evidence, not a live admission.

The 121-frame receipt envelope reports peak allocation above idle of about
2,404,414,464 bytes. Those are cumulative sampler/decode peaks, not an isolated
decode measurement and not a proven upper bound. The 4 GiB transient reservation
is deliberately larger. Before copying, require actual physical free memory to
cover actual copied tensors + 4 GiB + 2 GiB floor. Before each replica decode,
require 4 GiB + floor; check the floor again after completion and verify residency.
The selected settings refuse on any failure. CPU work does not prove the peak
stays inside that reservation. Qualification must report actual allocator peaks
and all four physical-free readings, including overlap with samplers.

The 1.0 GB graph cap is a soft post-capture cap. Existing receipts show about
3.43 GB reserved growth from the first capture. Moving display does not shrink
that graph pool. Qualification's xpu:3 eager reference can leave reserved memory
behind too, so recovery of the near-floor margin is uncertain. Do not remove the
dual walk, lower a floor or flush allocator caches to obtain a speed number.

## B. Drop read-ahead from the proposed launch

Use `LTX_ANCHOR_READ_AHEAD=0`. Keep the inherited implementation for explicit
119-compatible comparisons, with no claim that it is newly off-chain. The decode
thread's read/verify starts after receipt commit; it is not called synchronously
by the HTTP handler. Receipts record HTTP response construction, not socket flush
or client delivery. They cannot establish strict post-send ordering. There is no
measured net gain from paying for a second native read in advance.

The entire first-node-to-condition-A interval is about 0.124 seconds in dg0;
that is a loose upper bound on the included native read, not its isolated cost.
The corresponding 119 interval is only about 0.014 seconds shorter, while total
text+A preparation is unchanged. In particular, dropping read-ahead cannot be
credited with recovering the extra 0.09-second receipt bucket: that bucket is
before this work begins. No new asynchronous read thread is justified.

## C. Ordering changes are not supported by this timeline

The 119 upsampler is already fast and B overlaps the previous eager display.
Ordering upsampling ahead of display would postpone useful overlap; splitting
the decoder requires a new lifetime and numerical design. The measured loss
points to memory-triggered safety work. This packet tests residency separation
first, preserving all snapshot and pool policies. The inherited sampler-B option
remains available but is not recommended; a moved wait can delay the next cone.

## Predictions and comparison

These are preregistered estimates, never measured speeds. At 121 frames, predict
**5.10–5.40 seconds** per chunk (central 5.22) if replica qualification passes and
xpu:3 regains enough margin to avoid the extra dual walks. A conservative failure
range is **5.35–5.70 seconds** if reference allocations retain that pressure or
xpu:2 contention creates new waits. Dropping read-ahead has no assigned speedup.
The plausible saving is about 0.22 seconds of extra safety work, not 2.79 seconds
of display decoding, which is already largely overlapped. Neither range promises
real time: 121/24 is 5.041667 seconds; an anchored chunk adds only 120 new frames,
so sustained new video requires a period below **5.0 seconds**.

Compare the same scenes, seeds and chain start, including all byte hashes.
Use at least 100 interior chunks after the first ten and fresh-run repeats for a
speed verdict. Report period, display/next-cone FIFO wait, dual-snapshot frequency,
all-card memory and comparison failures. CPU test speed is not model speed.

[Contract](../recovery/20261010-continuation120-stream/CONTRACT.md),
[future launch reference](../recovery/20261010-continuation120-stream/LAUNCH.md),
and [build receipt](../data/resume-20261008/continuation120-build.json) bind the
final sources and seal. Open: full-model cross-card bytes, peak residency under
overlap, retained xpu:3 allocations, stable period and seam review.

## CPU build and seal

Prepared packet: `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-120`.
Manifest SHA256: `9af9330b7b9f08ad5c3b88d38b5c3f66186fab583d3b810afad7f0d61c5c328e`.
Plan SHA256: `585d6da602b87cc3f8d1440a19255c91b458f326efb2b1d2e97d6cc752072031`.

All **426 unique recovery tests** were validated. Full discovery ran 426 tests
with 425 passes and one stale source-structure assertion; after correcting its
call spelling, the complete 23-test decode module passed. The original failure
log remains in the build record. Builder 16/16 and session 17/17 also passed after
the final provenance-link correction. Client suites cover **403 checks**
(193 historical, 70 packet 119, 15 packet 119 HTTP, 101 packet 120, 24 packet 120 HTTP);
preflight adds **10/10**. Packet 120's 125 client checks were repeated with the
sealed manifest. Reruns are not added to the unique counts.

The builder recursively verified source closure and the exact parent, with zero
model requests. The packet and authoring directory contain zero `__pycache__`
or `.pyc` files. Both wrappers passed shell syntax checks only. Tests refuse
render-device opens, live addresses/port8188 and process signals. No launcher
or live preflight was executed. Full-model equality, memory and speed remain
unqualified, and the new decoder device remains off by default.
