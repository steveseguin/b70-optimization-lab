# First subsecond-goal campaign: exact repeats and bounded storage

September 13, 2026. User sharpened the target to one second of newly generated
video in under one second, at 24 fps, retaining quality/losslessness and a meaningful
resolution. Final output floor is 256x256. Three seconds is only an intermediate
marker. The user authorized small review samples and deletion of older footage.

## Result

All 30 requests completed on the existing PID 24848 without a restart, failure,
OOM or kernel device fault. Ten prompt/seed fixtures ran three times each.
Each captured tensor archive was independently checked for finite FP32 values,
exact dimensions, strict deterministic settings and its capture hashes.
Twenty-three independent pairwise receipts establish all 10 exact repeats:
boat/marble/bird also match their original-process references; seven new scenes
use their first current-split execution as their reference. No original-process
parity claim is made for those seven new scenes.

| Metric, 30 warm requests | Median | p95, nearest rank | Range |
| --- | ---: | ---: | ---: |
| Full decoded tensor archive ready | 6.386 s | 6.548 s | 6.237–6.561 s |
| Playable preview ready | 6.515 s | 6.680 s | 6.334–6.719 s |
| Client completion including history | 6.573 s | 6.983 s | 6.335–7.032 s |

Per-round preview medians were 6.598, 6.519, 6.401 seconds. This is unchanged
runtime support evidence, not a new speed optimization or subsecond result.
One GPU request runs at a time; encoding, sampling and decoding recompute.
The graph remains 256x256 / 25 frames / 24 fps, original BF16 checkpoint and 8+3 steps.
No continuous generation or endurance claim follows from this short sequence.

## Memory finding

Reported encoder offload grows from 690.00 to 2717.81 MiB. Its per-request
reported resident decrement is initially 45 MiB, then 90 MiB after the buffer
changes at request 13. Request 14 logs a real 0.98 MiB partial unload rather than
a fresh load report. Preserve that distinction; the summarizer leaves its
unreported offload total null rather than inventing a value.

The passive driver observations do not show a matching 2 GiB physical decline.
Encoder client resident VRAM oscillates between about 25,500 and 28,402 MiB;
the same upper value recurs throughout. Other device clients also show bounded
levels. Server RSS spans 20,940.68–20,971.80 MiB, and available host RAM remains
above 28,416 MiB. OS-managed process swap spans 7,867.59–7,878.16 MiB; swap settings
were untouched. Latency does not deteriorate over the three rounds.

This supports the [source-audit accounting hypothesis](encoder-source-audit.md):
the loader repeatedly subtracts its buffer from already-loaded weight accounting
without necessarily moving those newly excluded weights. fdinfo cannot establish
individual parameter devices or allocator live bytes. The CPU reproducer and
observations are useful evidence, not proof of every live internal transition.
The accounting issue remains unresolved in the running process. Do not promote
an endless-service claim or proceed directly to a long soak on these results.

## Retention

Verification preceded deletion. Exactly 30 campaign tensor archives and 27
campaign previews were removed: **607,014,535 bytes** reclaimed. The retained
three MP4 review samples total **169,913 bytes**. All original reference tensors,
the original lossless sample, and unrelated experiment/model files are untouched.
Per-output metadata, SHA256, actual comparison receipts, graphs, request history,
memory snapshots and deletion intent/completion receipts remain available.
These hashes preserve the identity of deleted footage; they do not make the
deleted bytes available for future rereading. Regenerate a deleted fixture when
visual review or another raw comparison is needed.

The pruning helper passed eight CPU tests covering failed gates, protected
paths, symlinks, traversal, changed files and narrow successful deletion. It
never follows a broad cleanup glob. On any failure the campaign halts new
requests and preserves unresolved output. No continuous recording is required.

## Next work

Two inactive source patches are preserved for review: correct repeated-load
accounting and crop unused all-layer hidden states before their CPU transfer.
The latter targets an untrimmed 735 MiB copy per 1024-token section without
changing encoder arithmetic. Its actual speed benefit is unmeasured. Both need
appropriate runtime quality gates; no patch was applied to loaded ComfyUI.
CPU checks now pass: eight retention safety tests, eleven crop/accounting
emulation tests and seven real-parameter ModelPatcher lifecycle tests. The latter
cover UUID changes, forced patching, partial unload and weight restoration;
[receipt](../data/stability-01/accounting-lifecycle-test.json). CPU load/offload
uses the same physical device, so accelerator residency is still unverified.
Prepare a bounded deployment/measurement packet next.
Keep startup-dependent work separate from live graph experiments; no further
server migration is scheduled by this result.

Evidence: [preregistration](../data/stability-01-prereg.json),
[summary](../data/stability-01/summary.json),
[full run/proof index](../data/stability-01/progress.json),
[deletion receipts](../data/stability-01/deletion-receipts.jsonl),
[post-run state](../data/stability-01/postrun-state.json),
[kernel journal](../data/stability-01/journal-after.txt).
Raw external root: `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/stability-01`.

Recompute the summary from existing evidence without GPU work:

```bash
python experiments/ltx25-b70/scripts/summarize-stability.py \
  /mnt/fast-ai/bench-results/ltx25-baseline-20260913/stability-01 \
  --output /tmp/ltx-stability-summary-review.json
```

Use a fresh output path. The runner itself is an exclusive 30-request campaign;
do not rerun it over existing evidence or treat a failure as a reason to retry.
