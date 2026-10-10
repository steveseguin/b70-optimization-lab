# Packet 121 continuation contract

Parent: sealed120, manifest
`9af9330b7b9f08ad5c3b88d38b5c3f66186fab583d3b810afad7f0d61c5c328e`.
The [120 contract](../20261010-continuation120-stream/CONTRACT.md) remains binding
except for these explicit changes. This is a CPU-prepared experiment; no new
length, cross-card output, memory peak, seam quality or speed is GPU-qualified.

Packet id121; prefix `stream121-`; comparison `stream-candidate-121-v1`;
qualification clip base12100000 and streaming base12101000. The 132 inherited
numerical identities remain unchanged; 145 frames adds44, making176. The plan
pins352 settings including text reuse and3168 qualification graphs, plus two
setup graphs. Plan SHA256:
`5c3aa526275b2e64e754b7c871cb4ce00f36d49888950df5f84d560b7727fd28`.

`LTX_STREAM_FRAMES` accepts49/97/121/**145**. Default49 remains for compatibility;
the first proposed command explicitly selects145. 169 is formula-evaluated only:
the conservative xpu:0 census falls0.095GiB below its8GiB floor. Contract, launcher,
client and output-node maximum refuse169. Changing the frame count changes the
qualification identity; a121-frame oracle or verdict cannot qualify145.

At145: latent T19, A/B video tokens304/1216, audio latent[1,8,151,16],
waveform[1,2,288480], images[145,256,256,3]. A frame-anchored continuation adds144
frames. Sealed formulas are unchanged; the first eager chunk must match all
measured tensor shapes and write `stream-geometry-measured.json`. All nine chunks
must pass eager/graph/repeat byte equality for latents, images, waveform and
anchors. There is no older145-frame full-model reference. Every cone chunk keeps
the display-last-frame byte check, including live chunks; failures latch.

The optional120 display replica extends from121 to121/145 frames, with the same
frame/cone/eager-display restriction and nine full-image cross-card comparisons.
The copied decoder remains BF16; native operation order, seed, encoder, samplers,
upsampler and graph/cone implementations remain inherited. No encoder moves.
The latch stays `display-replica-120-refused.json`; a new packet never clears an
inherited refusal. Every other existing latch and floor also remains unchanged.

The replica transient allowance is `4GiB * (T/16)^2`, rounded up:4GiB at121,
**5.640625GiB (6056574976 bytes)** at145. Before copying, require physical free
>= actual copied bytes + allowance +2GiB; before decode require allowance +2GiB;
afterward require2GiB. Qualification and live-receipt gates bind that exact
length-specific allowance and observed peak/reservation growth. This is a
conservative planning allowance, not a proven upper bound. Native peaks and
retained xpu:3 reference allocations can still refuse the optional arm.

First comparison:145/frame/dg0/cone/overlap1/prep1/fingerprint/no-cap/sampler-a/
read-ahead0/full/xpu:3. Full snapshots remain; no safety threshold changes.
The same server/client grammar as120 is retained. See [LAUNCH.md](LAUNCH.md).

The sink reads actual decoded preview frame count. Native audio is31.667ms short
of whole-video duration at145 and169; inherited sink behavior pads1520 samples,
then drops the overlapping frame and2000 samples. This preserves existing audio
behavior; it does not solve unconditioned audio across seams. Frame seams are
unchanged in kind, but longer prompt intervals still need owner viewing/listening.

`run_tests_121.py` blocks render-device opens, process signals and live sockets,
and guards Python children. Use `/home/steve/.venvs/ltx25-baseline/bin/python -B`
with OMP/MKL<=4. No launcher or preflight is a CPU test. The builder verifies the
exact parent recursively, preserves replaced bytes under `provenance/packet120`,
and writes an exclusive new destination. [Design](../../notes/2026-10-10-continuation121-stream-design.md)
and [build receipt](../../data/resume-20261008/continuation121-build.json) record
remaining gates, hashes and exact test counts.
