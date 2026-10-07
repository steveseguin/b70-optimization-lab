# Packet 100b: exact 20/28 screen, marginal gain; retain 23/25

Packet 100b completed **128 exact four-tensor comparisons** and a clean shutdown.
Its raw steady mean was **1.3006667 s/clip**, compared with
**1.3156404 s/clip** for the qualified 99b 23/25 control:
1.14% less time per clip (1.15% greater throughput). This is one
screen, not a robust improvement, record, or adoption. The p95 increased from
1.573 to 1.594 seconds. The approximately 9% preregistered
projection was not realized.

The [hash-bound closeout](../data/resume-20261007/closeout-100b.json) binds the
raw timing, complete summary, all 128 parity receipts, capture/freeze records,
process and packet identities, FD observations, campaign logs and postflight.
The sealed packet manifest is `50beee86e0ea22d7ef2405dcb4af56631a6eab7258c4052fbfb06214381aef63`.

## What was tested

This was the current ComfyUI `b00c6e95279053474955540ba4f551646722b9aa` path
with the qualified 99b process-local RoPE arithmetic compatibility retained:
BF16, 256×256, 25 frames, 8+3 sampling schedule, B1, two sampler workers with
shared pools, and a decoder replica on card 2. The named `two-way20-28` placement
moved three blocks from card 0 to card 1. The only additional source correction
was host ownership validation for a named two-segment route with one secondary
owner, in both host-node mirrors. The
[failed packet 100](2026-10-07-rebalance100-setup-failure.md) remains preserved;
it did not produce a performance or quality result.

The two self-check clips, ten fixture-probe clips and 116 timed emitted clips
all matched the original w93c references exactly for video latent, audio latent,
images and waveform. All ten context sentries matched across probe and timing;
decoder placement passed for all 128 clips. Freeze verified 48 routes and all
four worker/card graph chains. This establishes exactness for these fixtures
and this configuration, not other sizes or general upstream compatibility.

## Timing and the third-worker decision

The 120 timed prompts emitted 116 distinct clips after four pipeline fills.
The raw timing definition uses intervals between consecutive distinct output
completion timestamps and excludes the first interval from the steady mean.
There are 115 raw intervals and 114 in that mean; no host-stall intervals were
excluded. Effective generation rate was 19.221 frames/s, below
24 generated frames/s. The 24-fps playback setting is not generation throughput
or request-to-first-output latency.

Mean sampler occupancy was 1.994 jobs;
sampler-job median was 2.5068 s. Card 0 remained the
busiest sampler card at 1.1996 CCS s/clip and **0.9223 CCS utilization**; card 1
reported 1.0515 CCS s/clip and 0.8084 utilization. These counters are scheduling
evidence, not a strict physical speed bound.

**W3 is NO-GO under the [screening heuristic](2026-10-07-third-worker-decision.md).**
Only about 7.8% apparent card-0 idle capacity remains before extra contention;
the screen does not support a greater-than-5% gain with convincing margin.
This is a prioritization decision, not proof that W3 cannot help. No W3 run or
new W3 memory admission was performed. Actual freeze free memory was
9.778 / 10.073 / 9.741 / 14.740 GiB on cards 0–3; the second worker's incremental
pool usage was 0.2614 / 0.2350 GiB on cards 0/1, which is not a bound for a third
worker. Memory capacity alone is not the reason to stop this lever.

## Shutdown and continuation

After queue and worker quiescence, the runner sent one SIGINT at 14:45:13 UTC;
the process was gone at 14:45:18 UTC, with campaign and stop return codes zero.
[Four-card postflight](../data/resume-20261007/postflight-100b.json) passed at
14:46:07 UTC with no GPU fault lines during the probe or earlier this boot.
The FD observer recorded 473 samples, peak 2,633 descriptors, no alert, empty
stderr and a structured process-exited record. This bounded result does not
establish that descriptor growth or leakage is fixed.

Close **20/28 tuning**, while continuing the LTX lane. Preserve the exact 100b
packet, retained representative outputs and all compact receipts as research. Retain the
[qualified 99b 23/25 baseline](../data/resume-20261007/closeout-99b.json) for the
next separate 640-resolution qualification; neither the 256 timing nor its
exactness transfers to that size without measurement. No baseline promotion
or speed-record submission follows from this screen.

After clean shutdown, the coordinator retired 106 redundant whole tensor archives
(timed indices 14–119) from each of 99b and 100b, reclaiming 4,280,992,320 logical
bytes in total. Fresh whole-archive hashes matched retained references before
deletion; request/process bindings and the stopped PID were checked. The
[99b receipt](../data/resume-20261007/99b-retirement-receipt.json) and
[100b receipt](../data/resume-20261007/100b-retirement-receipt.json) preserve the
exact inventory. All first ten timed fixture samples, references, metadata,
previews, fills, self/probe captures and failures remain, including all 128
100b parity receipts. No models were deleted.
