# LTX resumed control — October 7, 2026

The corrected historical control passed and stopped at 13:07 UTC. The next
step is current-upstream qualification, followed by the planned sampler rebalance.
No new speed record or larger-size quality qualification is claimed.

## Result and scope

Native distilled BF16 revision `5e6e71018ee1756ed329b697a7b4aedc934dfce9`,
256×256, 25 frames at 24 playback fps, unchanged two-stage schedule and accepted
short-window w93c encoder. Two sampler workers, batch 1, shared pool, 23/25
block placement, decode replica on card 2. Packet 98 manifest remains
`918b47a5530b4dc97fe8fc8f4ec77fd64521ec6846217c54f5fba589e0e8377f`.
The process-local tqdm exception cleanup is additionally bound by
[its receipt](../data/resume-20261007/runtime-overlay-r2.json); the historical
server identity alone does not describe that overlay.

The 120 timed prompts emitted 116 distinct exact clips after four pipeline-fill
prompts. Ten probe clips and two self-check clips also matched. The context
sentry passed all ten fixtures; capture, decode placement and graceful-stop
gates passed. All four image/video-latent/audio-latent/waveform tensors retain
exact accepted-reference bytes. The timed mean is **1.317859649 s/clip**, or
**18.970153625 generated frames/s**, with p95 interval 1.764 s. The unchanged
metric excludes the first distinct-output interval; it measures independent
clip throughput, not request latency or coherent scene continuation. The prior
completed 1.3082 s/clip result is close; this single repeat does not establish a
regression or speed improvement.

[Complete campaign summary](../data/size-98/two-way-w2-b1-p1-dxpu2-s256x256-r2/summary.json)
and [closeout](../data/resume-20261007/closeout-r2.json).
Card 0 remains busiest: compute-engine seconds per clip 1.224 / 0.968 / 0.895 /
0.856; sampler job median 2.5532 s, about 1.993 sampler jobs in flight.
The [20/28 plan](2026-10-07-two-way-rebalance-plan.md) remains a projection,
requiring a separate new-base control before candidate comparison.

## Reliability and storage

The first attempt failed in application journal observation with EMFILE under
its 1,024-file soft limit; no GPU fault occurred. Evidence, a single graceful
shutdown and passing four-card health check are preserved in
[the incident closeout](../data/resume-20261007/fd-incident/closeout.json).
The separately preregistered corrected application used soft/hard limits
65,536 / 1,048,576. Read-only observations peaked at 2,636 descriptors across
497 valid samples. No alert occurred. At teardown the external observer got
PermissionError reading `/proc/3057550/fd`; the raw traceback remains at the
end of its observation file. This does not invalidate completed tensor checks,
but is not proof of leak-free behavior. The observer now reports that exit race as structured JSON after one identity recheck; unresolved observation loss exits nonzero. CPU child and failure simulations passed.

After proven queue/job quiescence, one SIGINT stopped the server. All four cards
passed [postflight](../data/resume-20261007/postflight-r2.json), with zero GPU
fault lines this boot. No reset, reboot, power or host-memory change occurred.

After shutdown, fresh byte hashes and provenance checks admitted 106 duplicate
timed tensor archives for retirement. Parent review checked the exact request
names (timed 14–119), retained all ten first-per-fixture samples and references,
then applied the hash-bound plan. **2,140,496,160 logical bytes** reclaimed;
all metadata, previews, fill/setup captures and failure evidence remain.
[Plan](../data/resume-20261007/r2-retirement-plan.json),
[receipt](../data/resume-20261007/r2-retirement-receipt.json).

## Next source base

A separate source-only tree at
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-upstream-99-source`
uses upstream `b00c6e95279053474955540ba4f551646722b9aa` with the accepted overlay
transplanted. All 1,501 old packet entries are accounted for; 1,333 current source
files include five native overlays and 63 lab additions. Fifteen independent
CPU checker controls and five builder controls passed. The actual source and
retained archive passed [independent verification](../data/resume-20261007/source99-verification.json).
This is source integrity only, explicitly unsealed and not launchable.

New upstream imports `comfy_aimdo.storage`, absent in installed 0.5.3; upstream
requires 0.5.5 and comfy-kitchen 0.2.37 rather than installed 0.2.33. Prepare a
separate dependency overlay, leaving the baseline virtualenv and Torch/XPU
unchanged. The transition-aware runtime packet must preserve model, graph,
health, memory, source and quality gates. The current source API review supports
narrow source-hash updates and a fail-closed native-attention-backend check;
new-base exact replay remains mandatory. Do not treat successful source merging
or dependency imports as quality or speed evidence.

### Additional completed-output retirement

The same strict helper subsequently verified all 593 emitted clips of the completed
600-prompt packet-97 batch-2 repeat against its retained batch-2 references.
It proposed 583 repeated tensor archives, keeping the first ten outputs, one per
fixture. Parent review checked the exact names (timed 17–599), complete emission
sequence, absent server PID and full archive hashes before applying the plan.
**11,772,728,880 logical bytes (10.96 GiB)** reclaimed, leaving about 65 GiB free.
All references, selected samples, requests, comparisons, metadata and previews
remain. This only retires redundant bytes; it does not promote batch 2 as exact
to the different accepted batch-1 outputs.
[Plan](../data/resume-20261007/packet97-b2-retirement-plan.json),
[receipt](../data/resume-20261007/packet97-b2-retirement-receipt.json).

The isolated full pinned application dependency overlay has a 600 MiB allowance
for exact downloaded wheels, extracted files and receipts. The baseline virtualenv,
Torch and XPU stack remain untouched; next GPU control separately needs 4 GiB
and the 50 GiB reserve.
