# Decoder axis cache: exact native screen with a small speed gain

2026-09-14. All11 packet10 screen clips matched all four original raw outputs.
The three scoped original/cache/original comparisons favor the axis cache in
both decoder and preview event intervals. This is a small native screening win,
not a promoted speed record or continuous video qualification.

| Scene | Original / cache / original preview seconds | Cache minus adjacent control mean | Decoder interval change |
| --- | --- | --- | --- |
| boat42 | 6.567458 / 6.338998 / 6.601771 | −245.616 ms | −83.436 ms |
| marble17 | 6.482009 / 6.445578 / 6.630246 | −110.549 ms | −77.339 ms |
| bird123 | 6.345577 / 6.296692 / 6.486862 | −119.528 ms | −97.789 ms |

Median paired changes are −119.528ms preview and −83.436ms decoder. Optimized
preview intervals span6.296692–6.445578s for25frames at24fps. The first bare boat
clip included initialization and took87.204714s; the second took8.564773s.
Neither bare interval is used as the steady-state speed denominator. Timings
come from client-received node events and include diagnostic overhead; they
are not isolated kernel durations or lossless streaming delivery measurements.
Three pairs cannot establish uncertainty or rule out order effects. Next is a
predeclared18-request balanced confirmation using the same running application.

The model/quality recipe remains native LTX2.5 distilled22B BF16,25frames,
256×256 final,24fps,8+3 sampler steps, original transformer dispatch. Sharding
remains21/27 of48 blocks onXPU0/1, text encoder onXPU2 and VAEs onXPU3. No prompt,
latent, output or cross-request mask cache was added. The cache retains only
axis visibility within one neighborhood-attention invocation; arithmetic and
the SDPA sequence remain unchanged.

Each clip was compared byte for byte against its registered original fixture:
F32 images[25,256,256,3], video latent[1,128,4,8,8], audio latent[1,8,26,16],
and waveform[1,2,48480]. Strict deterministic capture, finite/shape metadata,
model identity, original submitted graph and resident owners all passed.
All nine scoped decoder invocations matched the source/config-derived ordered
24-call sequence onXPU3 with BF16 inputs/outputs, including causal flags,
kernel sizes and scale. Their sequence hash is
`9d35c9062f136ea6c28212178586b235ca51bca5904c1d27bc6fe5239f4f54d6`.
These observations qualify the tested clips, not every prompt/device/runtime.

Client exec80638 exited0. Packet10 PID84255 remains idle in server exec33936 at
`http://127.0.0.1:8188`, original transformer dispatch and original default NA
route. All four render devices are owned only by that PID, queue empty, same
computer boot, no kernel fault or FAULT latch at16:42UTC postflight. No further
application reload is needed for confirmation.

Identity:

- Packet manifest:`d6ec6c63869d30dbe009708095f53811372e228becf16b7475ad30d11213fe6a`.
- Server identity:`1b3c4c36e6b91556b731057e725a52ef602ad16c397c842e270f90a13ef72cd2`.
- Client:`28fd569ab0acecb10a9b59821a707eb917d80bb013bdb973d046a8e6ad074988`.
- Final progress:`a0da72e9a1a85086b41bb02c66e9eda63401a649b5795e0a63e46deceb244568`.
- External campaign:`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/na-axis-screen-01`.

The [terminal text export](../data/na-axis-screen-01-export/summary.json)
preserves350 files in a1,475,732-byte archive, SHA
`c8b0cf80eab96efbec59023df2a0d9d36a57d69a9d9bcc123fc31e6aa3109e07`.
Its inventory binds the exact requests, parities, source closure, startup and
postflight evidence. The exporter performs stable text preservation, not a
second native qualification. Root reviewed the exporter;23 stdlib checks passed.

The corrected packet and preserved09 startup refusal are documented in
[preparation10](na-axis-runtime-10-prepared.md) and
[failure09](na-axis-startup-09-failure.md). The first startup failed a wrong
source pin before any clip; the corrected source check now closes all seven
dependency edges and passes a regression that reproduces that failure.

All11 redundant raw archives were deleted only after actual full comparison,
with hashes and deletion receipts retained. Three latest passing MP4 previews
remain (160,318 bytes total). MP4 is a lossy review artifact; raw equality is
established by the capture/parity records and protected original tensors, not
by preview-file equality. Canonical references and prior lossless export
evidence remain intact. No recording accumulation or disk-setting change.

The north-star target remains new continuous video faster than24fps, at least
256×256, with exact quality and bounded memory/storage. This screen remains
far from one second of video generated in under one second. The next result
must preserve the gain under matched repeated timings before considering it
for the retained optimization set.
