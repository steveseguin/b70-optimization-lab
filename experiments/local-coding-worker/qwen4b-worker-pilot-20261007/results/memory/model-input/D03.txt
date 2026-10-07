# LTX resume handoff — October 6, 2026

The owner paused the four-card LTX lane for consolidation. New experiment
submissions are stopped and the packet-97 process has exited after **exactly
one graceful SIGINT**, with no new server started. The process had reached a
CPU progress-display lock stall after the disk filled. A bounded nonblocking
Python stack snapshot located the remaining worker in `tqdm` lock acquisition;
the other pipeline workers were waiting for jobs. Ten seconds of passive DRM
observations showed no active GPU work before the incident shutdown.

The [shutdown receipt](../../data/maintenance/consolidation-20261006/ltx-stop.json)
records `process_gone=true` after the zombie was reaped. Postflight found no
listener on port 8188, no render-node holders and no kernel GPU faults. No
hard-kill escalation, restart, reboot or host-setting change was used for this
shutdown. Do not launch packet 98 until the owner resumes the lane.

Read [CURRENT.md](../../CURRENT.md) for any later shutdown receipt and live
host state, and [the stop review](notes/2026-10-06-enospc-stop-review.md) for
the source-level limits. This is preserved research, not an instruction to
keep a resident service or launch a campaign. The two-card Qwen lane is separate.

## What is accepted, and what is still conditional

- Accepted reference identity: native distilled BF16 LTX 2.5 at revision
  `5e6e71018ee1756ed329b697a7b4aedc934dfce9`, 256×256, 25 frames at 24 fps,
  original two-stage sampling. The owner accepted the short-window encoder
  on October 4; its fixtures are
  [`data/stability-01-window-prereg.json`](data/stability-01-window-prereg.json),
  reference prefix `stability-01-w93c-`. Earlier padded-encoder references
  remain historical and cannot be compared clip for clip with this baseline.
- Packet 97 batch 1, two sampler workers, shared pools, second decode worker
  on card 2: **1.308 seconds per clip, 126/126 exact** against those accepted
  references. This is the latest completed accepted-reference measurement
  used here, not the incomplete repeat described below.
- Batch 2: **0.910 seconds per clip, 613/613 exact**, including proof clips.
  Batch 4: **0.808 seconds per clip, 611/611 exact**, including proof clips.
  Both are 600-prompt campaigns checked against their own batch references.
  Different matrix rounding changes the finished clips versus batch 1.
  Their adoption still needs the owner's quality decision; neither is silently
  promoted as lossless against the accepted batch-1 references.
- The batch-4 stream needed about four clips buffered for continuous playback
  at its average rate. These are independent clips, not demonstrated
  clip-to-clip continuation or subsecond request latency.

Evidence: [packet 97 results](notes/2026-10-06-packet-97-results.md),
[batch independence and output differences](notes/2026-10-04-packet-96-results.md),
[accepted window milestone](notes/2026-10-04-milestone-window-baseline.md).

## Prepared next experiment

[Packet 98](notes/2026-10-06-packet-98-build.md) adds a fixed output size per
server: 256×256, 512×320 or 640×384. It is built and sealed offline and has
**no GPU throughput or larger-size quality result**.

Sealed local packet:
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-size-98`.
Manifest SHA-256:
`918b47a5530b4dc97fe8fc8f4ec77fd64521ec6846217c54f5fba589e0e8377f`.
The builder, runner, CPU checks, memory basis and negative sweep outcomes live
in this lane; preserve `data/size-98-offline/` in full.

When the owner resumes LTX, first verify the current host and sealed packet
identity without changing power or memory settings. Use a fresh health
admission receipt. The first planned GPU experiment is the packet-98
**256×256, two-way layout, two workers, batch 1, shared pool, decode replica
on card 2** control against `w93c`. Only after that control passes should the
predeclared larger-size plan proceed: first one worker/batch 1 at 640×384,
then the admitted two-worker/batch-2 case. The build note holds exact commands
and disjoint output indices; never reuse an existing run directory.

Larger-size arms are explicitly **speed only**. Their replay and cross-card
decode checks establish internal consistency, not reference parity or image
quality. Two-worker/batch-4 at 640×384 is refused by the current memory plan.
Do not bypass that refusal or convert estimated headroom into a measured claim.
Baseline adoption and clip-to-clip continuation remain separate decisions.

## Consolidation and incomplete-run evidence

An isolated [progress-lock recovery candidate](recovery/20261007-progress-lock/README.md)
now reproduces the installed progress bar's ENOSPC lock leak and fixes exception
cleanup, with ten passing CPU tests. It has not been installed or added to a
sealed packet. Review it for a successor runtime when resuming; it does not
repair the incomplete outputs or establish GPU correctness.

The October 6 disk-full cleanup revealed an empty source helper and an
unfinished packet-97 repeat. The recovery inventory and guarded CPU test are
recorded in [`data/consolidation-20261006.json`](data/consolidation-20261006.json).

- `scripts/ltx_output_size_98.py` was zero bytes. It was recovered from the
  exact sealed packet file only after verifying both the manifest and its
  per-file hash. Recovered SHA-256:
  `895b1c02ac764838b5d69446b0e5cf054884b191dd8b9446c5ce641ec40f2e52`.
- `data/place-97/two-way-w2-b1-p1-dxpu2-r2/summary.json` was empty and the
  timed-throughput receipt was absent. Its engine log has 541 complete JSON
  rows and a truncated final row. Preserve those original bytes; do not
  invent or promote a summary from the earlier probe. The completed packet-97
  results above are independent evidence.
- Three empty legacy CPU sweep logs are retained with their recorded sweep
  outcomes; an empty log is not a passing test. The broad sweep's historical
  failures and timeout remain negative evidence.

For a bounded CPU recheck, run `scripts/test-packet98-size-cpu.py` with the
baseline virtualenv Python, `-B`, and `scripts/cpu-guard-98.py` installed as
`sitecustomize.py` in a disposable `/tmp` directory on `PYTHONPATH`.
Use a 180-second subprocess timeout. The guard prevents accelerator calls,
endpoint connections, real checkpoint reads and writes outside `/tmp`.
Capture output to a new log; do not rerun the broad sweep just to repeat
already-recorded failures. The historical verification driver
`scripts/verify-review-98-cpu.py --tests` overwrites its prior receipts, so
preserve those before any deliberate rerun.

## Preserve on disk

Keep the model tree, original tensor/reference archives, all prepared packets,
the virtualenv and source tree, packet manifests, raw run receipts and fault
evidence under the linked storage paths. Nothing here authorizes model or
research-output deletion. Follow the current storage map and verified restore
receipts before any later archive move.

Host mitigations are already recorded in `CURRENT.md`: automatic bad-memory
fencing at boot, kernel 7.0.0-39 and the existing application deferred-backing
setting. Recent completed packet-97 runs reported no GPU fault or lockup.
This does not establish permanent hardware repair. Preserve settings and halt
new requests on a fault; no restart chain, automatic reboot or driver reset.

For future graceful shutdowns, packet 97's `stop_when_proven` in
`scripts/run-campaign-97.sh` is the source of the protocol: stop submissions,
prove an empty queue and completed stage jobs (or stable pipeline idleness),
recheck the fault latch and exact PID/start identity, send one SIGINT, and
wait at most 180 seconds without escalating to a hard kill. This is a protocol
reference, not a command to rerun the campaign or assume a historical PID.
