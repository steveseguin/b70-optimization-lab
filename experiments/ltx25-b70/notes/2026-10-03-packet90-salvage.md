# Packet 90 endure: offline salvage after the 09-21 freeze (written 2026-10-03)

The f90 campaign (`prepared-encoder-sentry-90`, server run dir
`encoder-server-sentry-90`) froze the host during endure prompt 118 of 120 at
03:29:53 EDT on 2026-09-21. The runner never reached its post-loop compare, so
it wrote no endure verdict. The tallies below were made offline on 2026-10-03
by an Opus subagent (read-only, tensors hashed on CPU through
`safetensors.numpy`); its scripts are not committed. They are the agent's
verdicts, not the runner's.

R = `/mnt/fast-ai/bench-results/ltx25-baseline-20260913`.

## Mapping used

`pipeline-decode-<prompt>.json` -> `detail.emitted_index` - index_base;
fixture = emitted % 10. With the sampler at depth 2 and decode at depth 1,
prompts 00-02 are fills and **prompt N emits clip N-3** (the packet 89 note's
"N-1" described a different depth arrangement).

## Exactness

| Prompts | Clips | Verdict |
| --- | --- | --- |
| warm 00-02 | none | three fills; the warm arm verified zero clips, so its `all_exact: true` is vacuous |
| endure 00-02 | none | fills |
| endure 03-88 | 0-85 | 86 exact: summary sha256 equals the reference on all four tensors and the raw `tensors.safetensors` re-hash matches the summary |
| endure 89-103 | 86-100 | 15 exact by the run-time summary hashes only; the raw tensor files are NUL from byte 8 MiB on (never written back before the freeze) |
| endure 104-117 | 101-114 | unverified: history, result, decode receipt and summary are 0 bytes, tensors all NUL |
| endure 118-119 | - | never completed |

No mismatch and no non-finite value in any surviving record. Independent
check: in all 103 sampler receipts (`pipeline-sampler-f90-endure-02..104`),
`detail.emitted_sample_output.video_sha256/audio_sha256` equal the fixture
reference latents, covering clips 0-102.

## Sentries

Sentry 1 (worker) recorded 104 clips, all finite. Sentries 2 and 3 raise on
mismatch; all 108 surviving sampler receipts and 107 decode receipts have
`passed: true`, `save_failures` empty, no `FAULT.json`, no latch. 101 clips
passed all three sentries and were oracle-exact.

## Wrong-clip bug

Not observed. Bird clips 2-82 exact (full), 92 exact (summary hash), 102
exact at the latent level only, 112 unknown. Per the design note's outcome
table this is the "bug silent under sentries" branch: the race is
timing-sensitive, or 100 clips is too few (previous rate about one per run).

## Timing

Intervals between `execution_success` of distinct emitted clips, prompts
03-103: n=99, median 1.597 s, mean 1.684, p95 2.277, worst 3.334. Reference:
f84 median 1.571 (n=115), f89 1.637 (n=111). The sentries cost nothing
measurable. No stall after prompt 11.

`scripts/analyze-phases.py` over `emitted_phases` (wall between marks, not
occupancy): job median 2.671 s, stage_a 1.680, upsample 0.032, stage_b 0.840.
The analyzer's steady filter (`emitted >= 2` on absolute indices) excludes
nothing; fix before reuse.

## Not established

**Busy-window attribution.** The packet that ran is the sentry build. The
per-replay `route_busy_ms` timers and the decode vae/save split are on the
unmerged branch `origin/packet-90` (6296a0e20, de11c53dc, 99f4940fe) and were
never in a launched packet. The 0.7 s/pair packing loss is still
unattributed, and the decode job (median 1.605 s) is still unsplit.

## What the freeze left

Last flushed prompt f90-endure-103 (03:29:30). 209 zero-length files; the
journal for boot dde38282 ends 03:25:01. That gap is journald's default
five-minute sync interval and ext4 delayed writeback, not evidence that
storage stalled first: see
[the 10-03 host review](2026-10-03-host-forensics-and-catch-up.md).
