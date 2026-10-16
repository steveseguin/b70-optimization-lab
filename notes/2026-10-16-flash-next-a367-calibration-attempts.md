# Flash-Next A367 zero-generation calibration — device attempts on October 16, 2026

All three attempts ran on boot `2cba7160` (kernel 7.0.0-39). That boot followed the owner-authorized reboot. Each attempt had:

- a fresh four-card health pass (zero fault lines);
- the 305 s stop gap;
- a payload receipt from 13:41:15 UTC (valid for one hour);
- a storage receipt on `/mnt/raid-models`.

No attempt sent a generation request.

| Attempt | Run | Launched (UTC) | Result |
|---|---|---|---|
| 1 | `flashnext-a367-calibrate-20261016T133433Z` | 13:47:13 | Stopped at 13:48:27, before any worker started. The 121-char vLLM ipc path exceeded the 107-char Unix socket limit. |
| 2 | `a367-20261016T135036Z` | 13:59:01 | Stopped at 13:59:12. The sampler hit ESRCH on a host process that exited mid-scan and sent SIGINT during `torch.xpu` device enumeration. |
| 3 | `a367-20261016T142901Z` | 14:34:26 | See below. |

Attempts 1 and 2 left zero GPU fault lines and no surviving owners. Their reviews are in:

- [attempt1-review.json](../data/2026-10-16-flash-next-a367-reseal/window-20261016T133433Z/attempt1-review.json);
- [attempt2-review.json](../data/2026-10-16-flash-next-a367-reseal/window-20261016T135036Z/attempt2-review.json).

## Fix and reseal (`440daf116`)

- `snapshot()` now skips `ProcessLookupError` (getsid ESRCH), as `window_driver.owned_session_gone` already did. Missing rank samples still fail the plateau gate.
- The launcher refuses an output path whose `<output>/scratch/rpc/<uuid>` would exceed 107 characters. The runbook output name is now `a367-$FN_STAMP`.
- Two regression tests were added. 147 CPU tests pass with zero seal mismatches. [Receipt](../data/2026-10-16-flash-next-a367-sampler-fix/cpu-tests.json).
- The calibration seal changed from `a15e5223…` to `0ad3948b…`. The owner approved the new hash-bound 114,000,000 KiB sentence ("Approve as written"); the record is [owner-approval-20261016-reseal2.json](../data/2026-10-16-flash-next-a367-reseal/owner-approval-20261016-reseal2.json).

Retrying attempt 2 unchanged was rejected. Had the race tripped during weight load, it would have sent SIGINT to a loading four-card server, which is the incident-5 pattern.

## Attempt 3 (seal `0ad3948b`)

Workers started at 14:35:46 UTC. GPUActive rose to 86.4 GB at allocation, before the shards loaded. That GPUActive is the designed UVA host-resident expert rows (see the 2026-10-08 correction in the host-RAM shadow note), not a deferred-backing shadow.

For the first ~3 min the load ran at 11-16 s per shard: the ranks were re-reading shards through the FUSE page cache. It then sped up to about 1 shard/s. Every rank finished loading at 14:46:59, in 672.6-673.2 s, holding 29.4-29.6 GiB each. September's load took 688 s.

MemAvailable fell from 118,707,644 KiB to 16,950,212 KiB. That is a decline of 101,757,432 KiB, leaving 4,950,212 KiB above the live reserve.

At 14:49:43, during the first graph-capture warmup, rank 0 raised `FileNotFoundError` on `<output>/scratch/triton/<hash>/_qsa_merge_splitk_kernel.llir`. The four ranks were compiling into one cold Triton cache on the ntfs-3g raid mount. Triton publishes cache files with `os.replace`, and rename-over on ntfs-3g is not atomic.

Engine init failed and the loaded four-card server exited with zero GPU fault lines. That is useful evidence for this lane's exit-fault history. Review: [attempt3-review.json](../data/2026-10-16-flash-next-a367-reseal/window-20261016T142901Z/attempt3-review.json).

**Fix `a6b6d14b5`:**

- Every scratch environment path now points to local ext4 at `/home/steve/.cache/a367-scratch/<run>`. That covers the hf, vllm, inductor, triton and xdg caches, plus `TMPDIR` and the rpc socket.
- The trace, logs and samples stay on raid.
- `load_and_plateau_seconds` rose from 1200 to 1800. Capture started at 895 s on a cold cache, so the old budget could have sent SIGINT mid-capture.
- 149 CPU tests pass.
- The new seal is `b75d9f86`, with preregistration `d5959d82`. The owner approved the new sentence (record: `owner-approval-20261016-reseal3.json`) and then said "if you run into an issue, fix the issue. simple".

**Note for the floor proposal.** The preregistered need formula is decline + 12,000,000 + 8,388,608 KiB. On attempt 3's partial decline that already gives about 122.1M KiB, above this host's ~118.7M KiB baseline. With the 10 GiB memory fence in place, the derived packet-4 fixture floor may not be satisfiable as written.

## Attempt 4 (seal `b75d9f86`)

Attempt 4 launched at 19:07:15 UTC. It had a fresh payload receipt (19:01:46), a health pass (19:02:03) and the 305 s gap. Workers were loading by 19:08:51, with scratch confirmed on local ext4.

**Result: PASSED.** `calibration.json` has passed, ready, clean_exit and gap_complete all true, generation_requests=0, and the unit exited with status 0.

| Phase | Time (UTC) / value |
|---|---|
| Weights loaded | 556 s (model loading 675 s per rank, 29.4-29.6 GiB) |
| Graph capture | 44 s (FULL, sizes 1/2) |
| Engine init | 322.7 s |
| Application startup complete | 19:25:38, about 1070 s after launch |
| 20 s plateau, then one SIGINT | 19:25:59 |
| All session owners gone, returncode 0 | 19:26:14 (15 s teardown) |
| 305 s post-exit watch | ended 19:31:19 |
| GPU fault lines on this boot | 0 |

Memory (2,235 samples, max gap 0.525 s):

- MemAvailable baseline: 121,638,400,000 B.
- Minimum: 16,329,396,224 B, reached at shutdown. The phase minima were loading 16.57 GB, plateau 16.56 GB and shutdown 16.33 GB.
- Observed need: **102,840,824 KiB**.
- GPUActive peak: about 86.9 GB, from the designed UVA expert rows.

Evidence (the raid originals are hash-pinned):

- [window-20261016T145417Z/run/](../data/2026-10-16-flash-next-a367-reseal/window-20261016T145417Z/run/);
- `/mnt/raid-models/bench-results/a367-20261016T145417Z/`.

This is the first measured clean load → ready → SIGINT → exit of the certified A367 recipe since the October exit-fault incidents. It is the safe-lifecycle evidence the FP8 return survey asked for.

## Floor derivation

The sealed `derive_floor.py` refused with "environment audit failed". The launcher's `environment.json` (from `window_driver.verify_environment`) has no aggregate `passed` key, because that function raises on any mismatch. The derivation test used a mock `{'passed': True}`, so it was blind to the real schema. Editing `derive_floor.py` would change the seal, and `derive()` refuses any seal other than the run's own.

So [derive_with_audit_schema_fix.py](../data/2026-10-16-flash-next-a367-floor-derivation/derive_with_audit_schema_fix.py) does the following:

- derives `passed` strictly from the six recorded audit fields (2,305 source files verified and matched, kernel stage, collectives, model metadata, admission artifact hash);
- runs the sealed `derive()` / `write_proposal()` unchanged.

Fix `derive_floor.py` at the next driver reseal.

The proposal is in [proposal/](../data/2026-10-16-flash-next-a367-floor-derivation/proposal/): **123,229,432 KiB**. That is the need of 102,840,824 plus the 12,000,000 reserve plus the 8,388,608 fixture budget. This host has MemTotal 123,365,852 KiB with blocks 53-57 fenced, and about 118.8M KiB available at idle. **The proposed packet-4 fixture floor can therefore never be admitted here as written.**

Need + reserve alone is 114,840,824 KiB, which leaves about 3.9M KiB of start margin. With the 12,000,000 KiB live watchdog, a generation run would have about 3.8 GiB of headroom over the measured ready-state minimum. Any floor for generation runs is an owner decision. Nothing has been approved.

## Commit IDs after the October 16 rebase

Local commits were rebased onto `origin/main` (11 context-campaign/ctxkeeper commits from the two-card host). Sealed files and the hash-bound approval records keep the pre-rebase IDs. The mapping is:

| Pre-rebase | Post-rebase |
|---|---|
| 539b88ccd | 440daf116 |
| 7a901fef3 | a6b6d14b5 |
| 4bbb8e94e | 6706fae2f |
| 5efca23e3 | 8211cf629 |
| 701f77903 | 3ebb1e4ee |

Seals pin file bytes, not commits, so every seal is unaffected.

