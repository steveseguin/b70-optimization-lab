# Current-upstream RoPE compatibility control passed — October 7, 2026

Packet **99b restores the accepted output bytes on the tested lane**: 126/126
probe and timed clips, plus 2/2 full-path self-check clips, match the existing
w93c references across images, video latent, audio latent and waveform. No
reference was regenerated. The original packet99 remains a failed quality
experiment; its output tensors and failure receipts remain evidence.

The [identity-bound closeout](../data/resume-20261007/closeout-99b.json) binds the
128 four-tensor parity receipts, raw timing, intermediate fingerprints,
preregistration, source/dependency identities, campaign log and postflight.
The [campaign summary](../data/upstream-99b/two-way-w2-b1-p1-dxpu2-s256x256/summary.json)
reports no missing/failed arms, exact emission order, and identical context
sentries for all ten fixtures between probe and timed arms.

## What changed, and what this establishes

Current ComfyUI source remains
`b00c6e95279053474955540ba4f551646722b9aa`, with the accepted lab overlays.
All **1,333 source-file manifest entries match packet99**. The isolated current
application dependency overlay is unchanged. The only arithmetic compatibility
change is replacing the existing eager `apply_rope_split_half1` function's code
in the server process with the pinned former arithmetic, retaining its function
identity and aliases. No installed package or prepared source file was edited.
Normal backend initialization runs before the guarded installer and the final
server identity is written before model construction.

Comfy-kitchen 0.2.37 changed the former separate multiply/add expression to an
`addcmul_` path. CPU controls demonstrated rounding differences, including BF16
Q/K with FP32 rotary matrices. This GPU control now demonstrates that restoring
that helper is sufficient to recover the accepted full outputs for this lane.
It does not establish compatibility for every kitchen operation, shape, dtype,
backend, model or future upstream release. The startup identity correctly still
says `installed-unqualified`: it was written before the GPU qualification; this
closeout supplies the subsequent bounded result without rewriting that identity.

Six self-check input conditioning fingerprints now match old packet98-r2
exactly; all six differed in failed packet99. For boat and marble, the recorded
sampler input and stage-A/B context hashes also match packet98-r2. Boat's
conditioning returns from `4525b1eb…` to `ca4e9178…`, and both stage context
hashes return from `1032e454…` to `b318cf6b…`. Initial noise/seed identity was
already unchanged in packet99. These intermediate comparisons support the
localization; final four-tensor equality supplies the output gate.

## Throughput, without a new record claim

The unchanged workload is native distilled BF16 LTX2.5, revision
`5e6e71018ee1756ed329b697a7b4aedc934dfce9`, 256×256, 25 frames, 24 playback
FPS, original 8+3 steps, two-way 23/25 blocks, two batch-one sampler workers,
shared graph pools and decode replica on xpu:2.

The raw timed receipt records 120 submitted prompts and 116 emitted/verified
clips; four pipeline fills are excluded. Its unchanged definition measures the
interval between consecutive distinct emitted clips at server
`execution_success`, excluding the first interval from the steady mean:

| Measurement | Packet99b |
| --- | ---: |
| Steady mean seconds per clip | 1.315640350877193 |
| Generated frames per wall second | 19.00215357740544 |
| Steady p95 interval | 1.573 s |
| Steady maximum interval | 1.708 s |
| Wall seconds per second of 24-FPS video | 1.2630147368421052 |

Packet98-r2 measured 1.317859649122807 s/clip. The historical accepted packet97
headline remains about 1.308 s/clip. This is a successful source/dependency
compatibility control, **not a new speed record** or evidence that a roughly
0.17% difference from r2 is significant. These are independent short clips;
19 generated frames/s is not 24 generated frames/s, a fresh-request latency,
or coherent continuation. The original packet99 had no timed arm after its
quality failure, so there is no valid packet99 speed comparison.

## Shutdown and limits

The campaign log records proven quiescence followed by one SIGINT at
**14:12:02 UTC**; PID3129897 was gone at **14:12:07 UTC**. Campaign and stop
return codes were both zero. The four-card postflight completed at
**14:12:38 UTC**, all cards passed, with zero recorded GPU-fault lines this
boot. No restart chain or host-setting change was part of this control.

The external descriptor observer recorded 496 samples (33–2,634 descriptors,
last pre-exit 2,503), no 16,384-descriptor alert, and a clean
`process-exited` terminal record with empty stderr. This confirms clean observer
teardown for this run; **it does not prove a descriptor leak is fixed** or
establish long-duration stability.

## Pinned identities and next comparison

- Packet99b manifest: `f819270165a7e8c59206b0dd641ebb1b7763e586b458a1e32a75344f96220d0a`.
- Failed parent99 manifest: `e7b268d2e54e9010e88e325681a5d7af43052d7affdf803ca9b6c7ee54ed8736`.
- Isolated dependency receipt: `626dd5e9d840c6bfa56f6da23f326e2a434aae46c73b3662c5a08a3d50970e09`.
- Installer: `99e6bc916789b8d4443a869000af524462ce66eef4757f000280b8a80366c570`.
- On-disk 0.2.37 eager RoPE source: `630a3d287bf602046935086f9d43eb6db2ec4971913a1cb3fb35bae6ea4ac9ee`.
- Preserved 0.2.33 source supplying the old helper: `aee33a18bb5fe75ce24ebad389b830c9d5775d52723fc7df4864598547b2257c`.

This permits the separately identified **20/28 placement-only candidate** to
use 99b as its qualified control. It does not qualify that candidate in advance,
raise batch size, alter sampling, or admit larger-size speed-only arms as
lossless improvements. Keep full reference, replay, emission, memory and health
gates. The failed99 record is linked by the closeout and remains unchanged.
