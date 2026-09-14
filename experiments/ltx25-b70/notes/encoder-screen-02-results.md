# Encoder candidates: exact outputs, no convincing speed gain

September14: all25 requests passed strict original-reference comparison for
images, video latent, audio latent and waveform on PID78769. All four component
transitions passed actual CPU unload/ownership checks. The fixed campaign ended
normally, with the same process idle on the control variant and no fault latch.
This is the first native GPU qualification of the three encoder candidates.

| Arm | Warm preview median | Warm raw tensor median | Initialization |
| --- | ---: | ---: | ---: |
| Control before | 6.364 s | 6.247 s | 62.328 s |
| Crop before CPU copy | 6.377 s | 6.264 s | 100.253 s |
| Small-state residency/accounting | 6.430 s | 6.296 s | 69.391 s |
| Combined | 6.441 s | 6.310 s | 86.000 s |
| Control after | 6.643 s | 6.520 s | 84.902 s |

Each arm has four warm requests in the same boat42, marble17, bird123, boat42
order after one excluded initialization request. There is no promoted speed
winner: the bracketing control median drifts4.38%, and actual small-weight
placement changes during warm-up. The first warm boat cannot be compared with
a later candidate boat as though their warm state were identical. These small
samples do not support a full-suite or sustained-streaming speed claim.

The small-state patch does fix the measured accounting defect. All289 RMSNorm
weights and48 scalars (1,539,680 bytes, native BF16) stay on XPU2 in all ten
small-state/combined requests. Reported loaded bytes equal actual registered
resident parameter/persistent-buffer bytes on every request. Control/crop arms
instead acquire an accounting shortfall of45MiB per request, reaching135MiB by
their last request while actual resident bytes remain constant for the last
three requests. This is bookkeeping drift, not equivalent physical eviction.
The patch is a qualified mechanism/correctness result for these fixtures;
longer residency qualification and useful latency improvement remain separate.

Keep control as the compiler experiment reference to isolate the next change.
Do not spend another confirmation campaign promoting a neutral speed screen.
The next candidate is exact compilation of one native transformer block,
followed by full-clip original-reference checks only if the local gate passes.
The control-before node medians are about1.80s text encoding,2.53+1.00s sampling,
and0.61+0.18s video/audio decode. These client event intervals guide selection;
they are not synchronized kernel measurements. One second of new video in under
one second remains unachieved at the unchanged256x256/25-frame/24fps workload.

The harness deleted redundant raw archives only after exact comparison and
retains three final previews totaling150,332 bytes. Original references and the
previous strict-startup failure remain protected. MP4 previews are lossy review
media; the quality oracle is the exact raw float tensors, not the preview codec.
No computer reboot, power-setting change or application restart occurred during
this25-request campaign.

Evidence: [summary and all per-request times](../data/encoder-screen-02/summary.json),
[original-file checksum inventory](../data/encoder-screen-02/inventory.json),
[compressed original receipts/logs](../data/encoder-screen-02/evidence.json.gz),
[preregistration](../data/encoder-screen-02-prereg.json),
[exporter](../scripts/export-encoder-screen-02.py).
The archive contains246 original text files, including full placement/unload,
capture/strict flags, profiles, prompt/history identities, memory snapshots and
deletion receipts. It is a gzip-compressed JSON mapping of evidence-root-relative
paths to original text; decoding each value as UTF-8 reproduces its inventory
SHA256. Export verified every archived file through that roundtrip.
Full working evidence remains under
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/encoder-screen-02`.

Packet: prepared-encoder-03, manifest
`d391ac4236e7ea683af1e1cdae5a4f020e608e20c4ff849d9fe958b524d028e7`;
runtime/server identity is preserved in the summary. The launcher correction and
failed first screen are linked in [startup fix](encoder-strict-startup-fix.md).
