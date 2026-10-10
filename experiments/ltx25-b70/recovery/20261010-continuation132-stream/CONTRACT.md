# Packet 132 contract

Parent is sealed packet 131, manifest
`e25d8d623741fed31fccfd049a323e9bf853302a21aaff472c48eda40fb1ed6f`.
Preparation is CPU only. Native correctness, physical memory savings and speed
remain unqualified. No prepared command is executed during this work.

`LTX_AUDIO_RESIDENCY=legacy|xpu2` defaults to legacy. Legacy retains packet
131 placement. The independent xpu2 option moves only the audio VAE and
vocoder; the upsampler remains on xpu:0 and the video VAE remains on xpu:3.
It requires packet 131's fixed 145/frame/dg1/cone/bo1/pa1/fingerprint/full,
serial eager display on xpu:2, legacy auxiliaries, no read-ahead or pool cap,
`LTX_CONE_GRAPH_MEMORY=replica-release`, and display allocator release off.
An isolated timing control admits the same geometry with dg0 and cone memory off,
using the inherited GC10/cache0/parent maintenance scope. All original floor,
screening, fault, latch, storage and exact-output gates remain.

The audio checkpoint contains 364,666,868 bytes (0.339622486 GiB). This is
potential residency relief, not measured freed physical memory. Card 2's
workspace must be checked before and after audio work. Qualification compares
native card 3 and card 2 waveform bytes on the same input in the three eager
chunks. The separate reference returns to CPU before the first cone capture.
All nine captured outputs still pass the frozen-reference and three-chain
checks. No cached response, precision change or output acceptance tolerance.
Isolated reference/decode/transfer timing is qualification evidence only;
sustained audio/period timing is measured separately, by chunk parity.

`LTX_CONE_CAPTURE_RESERVE=parent|scaled-476` defaults to parent (5 GiB).
The proposed scaled-476 value is 5,111,011,083 bytes, rounded upward from
4.76 GiB. It is recognized but fails closed before any device action: the
saved 121-frame receipts do not establish a measured 145-frame peak or upper
bound. It cannot be enabled by an arbitrary number or environment override.
The 9 GiB floor and 0.75 GiB screening band never change. Parent's measured
post-capture growth and free-memory checks remain enforced.

Every option is bound in the inner plan, source closure, run naming (audio
suffix `-audioxpu2`), status, receipts, decode records, verdict and client
expectations. Audio legacy plus parent reserve is the packet 131 off form,
with packet 132's distinct outer identities and explicit option fields.
Malformed or missing candidate evidence refuses; there is no fallback/retry.

The encoder move is deferred: its shared encoder/decoder owner cannot be
split by a device-string substitution. No extra allocator reclaim is claimed:
packet 131 released zero bytes on card 3 and left 1.684774 GiB reserved unused.

See [memory evidence](../../notes/2026-10-10-continuation132-memory-evidence.md)
and [design](../../notes/2026-10-10-continuation132-stream-design.md).
