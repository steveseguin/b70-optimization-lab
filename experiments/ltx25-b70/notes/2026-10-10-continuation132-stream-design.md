# Packet 132: separate audio placement for the 145-frame cone graph

Packet 131 missed the first capture admission by 12,451,840 bytes. Its attempted
allocator release returned zero bytes on card 3 and left 1,809,012,224 bytes
reserved but unused. The deficit already includes the full 0.75 GiB screening
band. The [receipt audit](2026-10-10-continuation132-memory-evidence.md) records
exact before/after counters, source paths and hashes, two 121-frame capture receipts,
ranked remedies and encoder-copy accounting.

Packet 132 adds default-off audio placement without moving the upsampler.
`LTX_AUDIO_RESIDENCY=xpu2` relocates the audio VAE and vocoder to card 2 while
keeping the native BF16 arithmetic selected by the sealed `--bf16-vae` launcher.
The unchanged native audio node produces every candidate waveform. Checkpoint
residency is 364,666,868 bytes (0.339622486 GiB); this projects 0.328025807 GiB
above packet 131's original 5 + 9 + 0.75 GiB capture threshold. Allocator layout,
constructor state and simultaneous work can change the actual physical delta.

A separate CPU reference is copied before the native audio weights load.
For each of the three eager qualification chunks, this reference visits card 3,
runs the unchanged native batch-one arithmetic on the same CPU latent, and
returns to CPU. Waveform bytes, shape, dtype and sample rate must match card 2.
The registered candidate owner stays on card 2 throughout. The first cone
capture requires all three controls complete and no reference tensors on card 3.
The graph and repeat chains retain all nine whole-output/frozen-reference
comparisons. No reference decode is added after graph capture. Separate
before/after physical workspace guards retain the original card floors and
screening. Audio-reference admission may safely refuse before graph admission;
its precise boundary is not measured in the saved receipts.

`LTX_CONE_CAPTURE_RESERVE=parent` keeps 5 GiB. The proposed `scaled-476` value
is explicitly recognized and refused pending suitable 145-frame memory evidence.
Both 121-frame captures show 3,430,940,672 bytes reserved growth; multiplying by
(19/16)^2 gives 4,838,162,432 bytes (4.505889893 GiB), not a proven upper bound.
4.51 + 0.25 GiB rounds upward to 5,111,011,083 bytes. It would lower the budget by
0.24 GiB and project a combined 0.568025806 GiB margin, but no physical bytes are
freed by lowering an allowance. A postcapture growth check cannot prove that
an unmeasured preallocation allowance was safe. The successful audio-only
145-frame capture is the next opportunity to collect the missing evidence.

The video encoder could save 0.594066264 GiB, but it shares the video VAE owner,
loader and guards with the decoder. It needs a separate split-owner change and
native byte gate. Existing CPU anchor uploads/results can route to card 2 with
zero extra full-frame peer traffic; leaving normalization on card 3 would add 20,480
bytes per A+B chunk. This larger unqualified change is deferred because audio
alone covers the measured admission gap. More allocator release has 0 GiB of
verified extra benefit; no release loop or live-pool eviction is introduced.

The new modes bind through plan, run naming, status, receipts, decode records,
qualification verdict and client expectations. Audio legacy/reserve parent
keeps packet 131 behavior with a distinct packet 132 packet identity. Client pins use the
inner plan digest, never the envelope's file hash. Parent 131 is fixed at
`e25d8d623741fed31fccfd049a323e9bf853302a21aaff472c48eda40fb1ed6f`.
Every changed source is preserved against the parent in the new packet's
provenance. Its accumulating source closure needs 192 MiB build disk allowance,
up from 160 MiB; storage free reserve and runtime allowance rules are unchanged.
This is a source-copy budget change, not a host-memory setting.

The isolated timing arm uses 145 frames/dg0/serial replica 2 with GC 10/digest cache off/parent
maintenance and audio legacy versus xpu2; no bundled upsampler move. Measure
candidate audio-node time, reference transfers/decode/unload separately, and
sustained parity medians/p90/end-to-end periods on future authorized matching
servers. The graph candidate forecast remains 5.25–5.35 s per 6 s of video,
0.875–0.892 s/s, **plus unmeasured audio-placement cost**. Exact native waveform
parity, freed memory, capture peak, full qualification and repeated cadence
remain open. No GPU speed or memory measurement is claimed by CPU tests.

The [contract](../recovery/20261010-continuation132-stream/CONTRACT.md),
[launch text](../recovery/20261010-continuation132-stream/LAUNCH.md) and
[build receipt](../data/resume-20261008/continuation132-build.json) carry final
identity and exact validation counts. All work is CPU only with nice 19,
OMP/MKL 2 and pinned bin/python -B. No GPU, model/server launch, check-only,
systemd/unit, live port 8188, device-node, process-signal, host-setting,
existing-run or ltx-stream operation is authorized or performed. Own scratch
and Python caches are removed before completion.

Final CPU validation: 960/960 recovery cases in one full rerun; 5,677/5,677
client checks across 39 suites, including 28 inner-plan pin assertions;
10/10 mocked preflight checks; three runtime cases with 22 matching output
hash comparisons. Recursive verification covers 2,269 bound files and 2,271
physical files. There are no Python caches or remaining owned scratch.
The first recovery run passed 959/960: a mock deployed packet omitted the new
audio helper. Its corrected fixture passed 28/28 focused tests before the full
rerun. The historical packet 131 client fixture shadowed its packet variable
inside the all-pins loop; its corrected rerun passed 545/545. Both initial
failure logs remain. Neither correction changed sealed runtime or client code.
