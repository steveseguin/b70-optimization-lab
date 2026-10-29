# Cut 0/16/33/48 prefill screen: 3 targets + draft, 262K, 121,854/512 (2026-10-29 UTC)

**Verdict: mixed, leaning promote for long prompts.** Moving GDN layer 16 off stage0 cut TTFT by 3.90% and
request time by 3.60%, measured against a fresh control in the same session. All-511 decode was 3.32% lower, but
two control runs differ by 4.09% on that metric, so the decode change is within run-to-run noise. Full canonical
state and all 512 outputs are exact. There were no incidents.

## Setup (same as equal16; only cuts and output paths differ)

- **Binary:** 339b75. The plans come from a snapshot of commit 7e396b490, which matches all 260 compiled sources
  and every pin of the equal16 control plan; the live tree has since changed.
- **Policy:** reference routing; 256-row chunks, 4 slots, depth 3; measured checks on long arms. Targets
  23/27/47, draft 43. **Plans:** gate `aaca610f`, cut16 `7a3dd190`, control `141071b8`.
- **Units:** Restart=no, KillMode=process, SendSIGKILL=no, Nice=19, taskset 0-3,16-19, default NOFILE (as equal16).
- **Order:** one launch each, no retries: gate, cut16 long, fresh control long. All four card locks held
  throughout; host quiet during every timed arm.

## 1. Full-state gate (1677/32, qualification policy): PASSED

- **Owners and outputs:** all four owners exited 0; the 32 outputs match the retained 0/17/33/48 gate.
  **State comparison:** run against the PP4 serial reference with `dedicated-gate/compare.py`. 2,065 target
  sources, 0 errors; 73 draft sources (638.5 MB of bytes); 1,707 pairs, hash `e78b54ee…`, same as the 0/17/33/48 gate.
  Reference bundles (15.71 GB) restored from the HDD archive (checksums verified), released after the proof.

## 2. Timing (one first-inference request per arm; definitions from compare_reference_long.py)

| Metric | cut16 0/16/33/48 | fresh control 0/17/33/48 | change | retained control | drift (fresh vs retained) |
|---|---:|---:|---:|---:|---:|
| TTFT s | **240.963** | 250.751 | **-3.90%** | 250.842 | -0.04% |
| Request s | **252.329** | 261.739 | **-3.60%** | 261.382 | +0.14% |
| First-99 decode tok/s | 50.134 | 48.983 | +2.35% | 52.415 | -6.55% |
| All-511 decode tok/s | 44.988 | 46.533 | -3.32% | 48.515 | -4.09% |
| Decode window s (request - TTFT) | 11.366 | 10.988 | +3.44% | 10.540 | +4.25% |
| Owner lifecycle s | 475.21 | 483.64 | -1.74% | 482.73 | +0.19% |

**Outputs:** all 512 IDs are identical across cut16, the fresh control and the retained control.

**Prefill busy time per target stage (s):** cut16 232.57 / **237.99** / 211.37; control 248.29 / 218.41 / 211.72.
Stage1 is now the bottleneck. Layer 16 cost about 19.6 s on stage1, more than the 14.7 s the bubble analysis
assumed, so TTFT landed at 241.0 s rather than the predicted 236-239 s.

**Device census (GB):** cut16 22.69 / 25.00 / 23.85 + draft 3.75; control 23.93 / 23.79 / 23.85 + 3.75.
All arms stayed under the 30 GiB cap.

## 3. Long full-state proof (adapted compare_reference_long.py): PASSED

- **Sources, pairs, chunks:** 2,065 canonical target and 73 draft sources match;
  122,364 canonical pairs (hash `046dcd02…`, same as equal16's proof) and 476 native bulk chunks match.
- **Coverage:** all 16.37 GB of control payload bytes were streamed against their seals. The cut16 side was
  checked through its byte-verified archive receipt.
- **Scope:** the measured_target policy excludes inactive alternate banks and nonfinal head scratch.

## Comparison with equal16 (0/16/32/48, earlier session)

Equal16 had the better TTFT (236.21 s) and request time (248.72 s), but decode fell to 40.88 tok/s. Cut16 keeps
decode at 44.99 tok/s, within noise of the control.
- **Against equal16:** cut16 is faster once output exceeds about 2.1K tokens (simple TTFT + N/rate model).
- **Against the control:** cut16 is faster up to about 13K output tokens, if the 3.3% decode difference is real.

## Housekeeping and safety

- **RAM:** the coordinator moved tp-direct and the Oct-26 lab runs to HDD. I deleted 202 authorized stale-build
  entries (2.441 GB; recorded in `stale-build-deletions.json.gz`). Admission margin was 6.6-6.9 GB at each launch.
- **Archives:** each run's 5 state bundles (16.37 GB per run) were archived to
  `/mnt/raid-models/ownrt-experiment-archives/2026-10-28/` (cut16-gate-r1, cut16-long512-r1,
  cut16-control-long512-r1), byte-compared against the originals, then released. Receipts are in
  `*/archive.json.gz`.
- **Kept in /dev/shm:** metadata, transport maps and the snapshot. **Kernel log** 03:08:29Z-03:44:39Z: no
  entries. All passive postflights were clean.
- **Locks and marker:** card locks released at 03:44:38Z; marker removed at 03:44:39Z, after every started
  process had exited.

## Next

1. **Phase-specific cuts:** read the prompt on 0/16/32/48 and decode on 0/17/33/48. This needs new native
   state-handoff code.
2. **Balancing stage0 and stage1:** cheaper only if the lookup work on stage0 shrinks, since no integer cut gets
   below about 228 s.
3. **Decode noise:** repeat control decode runs before attributing a ~3% decode change to cuts.
Evidence: `gate/`, `cut16/`, `control/`, `tools/`, `index.json`, `summary.json`, `commands.txt`.
