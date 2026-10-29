# Prefill bubbles: 3 targets + draft, 262K, 121,854-token prompt (2026-10-28)

CPU-only reading of retained traces; no GPU, build, service or model access. Paths are relative to
`experiments/own-xpu-runtime/research/pp4-review-2026-10-28/`. Every number is produced by
`prefill-bubbles/analyze_bubbles.py` from the files it hashes in `bubbles.json`. "Busy" means the controller saw a stage
command in progress (send to reply), not GPU utilisation (`engine/planning/rolling_provider/dedicated_prefill_pipeline.py`
lines 34 and 52-62).

## Short answer

- **The current 3+1 prefill has no material bubbles.** Stage0 is busy 248.43 s of the 250.84 s TTFT (99.04%). Startup,
  drain, host hand-offs and the first token add 2.41 s (0.96%). The "1.3-1.5 stages busy" figure is the old PP4 wave.
- **Stage0 is the bottleneck.** A perfectly filled pipeline at these cuts takes about 248.4 s, so waves, slots and host
  overlap can recover at most about 2.4 s.
- What is left is **imbalance**: stage1 and stage2 wait for stage0 for 32.5 s and 39.1 s. Moving layer 16 off stage0
  during prompt reading is the one material exact lever: estimated TTFT 236-239 s.

## 1. Per-owner timeline: control run, cuts 0/17/33/48

Trace: `equal16-topology-screen/control-r1-evidence/control-output/dedicated-prefill-pipeline.jsonl.gz` (476 chunks:
475 x 256 rows + 252). TTFT 250.842 s and request 261.382 s: `driver-result.json.gz` in the same directory.

| Owner | Layers | Busy s | Busy % of TTFT | Idle in TTFT s | Mean ms/chunk | Starts at s | Ends at s |
|---|---|---:|---:|---:|---:|---:|---:|
| stage0 | 0-16 + lookup | 248.434 | 99.04 | 2.41 | 521.86 | 0.000 | 249.056 |
| stage1 | 17-32 | 218.327 | 87.04 | 32.52 | 458.66 | 0.550 | 249.518 |
| stage2 | 33-47 + final | 211.771 | 84.42 | 39.07 | 444.88 | 1.019 | 249.965 |
| provider | MTP replay | 171.191 | 68.25 | 79.65 | 359.56 | 1.475 | 250.333 |

- **Ramp:** each downstream owner starts one chunk later (0.55, 1.02, 1.48 s). **Steady:** stage0 is 99.6-99.8% busy in
  every tenth of the run; stage1 85-88%, stage2 82-85%, provider 66-69%; 3.39 of 4 owners busy on average.
  **Drain:** the last chunk passes through stage1, stage2 and the provider in 1.277 s.
- **TTFT parts (s):** request start to first chunk 0.105 + stage0 work 248.434 + stage0 hand-offs 0.622 + drain 1.277
  + last prompt row to first token 0.404 = 250.842.
- **Ideal wall** at these cuts = max stage busy = **248.43 s**. With perfectly balanced target work: 678.53/3 = 226.18 s,
  plus the measured 2.41 s overhead = **about 228.6 s (-8.9%)**.
- **Equal16** (cuts 0/16/32/48, `equal16-r1-evidence/equal16-output/`): busy 233.715, 222.590, 225.314, 170.764 s; TTFT
  236.209 s; stage0 still 98.94% busy. With 16 layers on every stage, stage0 still averages 490.92 ms per chunk against
  467.62 and 473.31 ms. Stage0 also does the embedding/PLE lookup (`equal16-topology-screen/screen.json` "timing.claim"),
  which fits that excess; the excess itself is not attributed.

## 2. What causes the gaps

| Suspected cause | Verdict | Evidence |
|---|---|---|
| Chunks in flight / transport slots | Not binding now | 0 lease-bound chunks; 0.027 s total issue gaps |
| Startup compilation | Fixed by AOT | First chunks now 398-541 ms |
| Draft-provider replay | Off the critical path | Provider 68% busy; only 0.36 s in the drain |
| Synchronous host waits | Negligible | 0.622 s on stage0, about 1 ms per chunk |
| Per-chunk checkpoint/seal work | Part of stage0's own work | See below |
| Stage imbalance from the cuts | **The real loss** | Stage0 1.138x stage1, 1.173x stage2 per chunk |

- **Slots.** The control ran 4 slots, peak 4 chunks in flight (`driver-result.json.gz` peak_unfinished_chunks). In
  `dedicated_prefill_pipeline.py`: line 90 allows one command per owner; line 91 makes an owner wait for chunk k from the
  owner before it; line 93 lets stage0 admit chunk k only while fewer than `slots` leases are held; lines 84-85 free a
  lease only on the provider's full ACK. `prefill.py` lines 14-16 allow only 2 or 4 slots. With 2 slots
  (`dedicated-gate/two-slots-control-long-r1-evidence/run/output/`) 348 chunks waited 292.5 s for a lease; stage0 was
  49.8% busy, 1.72 owners busy on average.
- **Compilation.** With 4 slots before AOT (`dedicated-gate/four-slots-long-r1-evidence/run/output/`) there was one
  112.9 s stall at the start; each stage's first chunk took 40.5-47.2 s (provider 33.4 s).
- **Provider.** Its sha256/record checks run before its timer starts (median 4.81 ms issue to start).
- **Checkpoint/seal.** Ring checkpoint capture runs only for tentative decode rows (`dedicated-timeline-screen.txt`), not
  in prefill. In the stage0 profile run the command took 525.29 ms per chunk and the profiled sites 493.82 ms; the
  31.47 ms (6.0%) difference (lookup, uploads, readback, bank swap, RPC) is unattributed. Routed experts, combine and
  gather are 51.75% of site time. Sources: `reference-one-row/router-tie-candidate/planner-policy/`
  `prefill-profile-r1-evidence/output/stage0/native/prefill-profile.jsonl.gz` and that run's trace in `prefill-bubbles/evidence/`.
- **Old PP4 numbers** (522.318 s prefill, 674.711 s target work, 437.279 s target-active; `candidate-long/matched-result.json`)
  come from `prefill.py` lines 175-206: `max_workers=2`, six barrier phases per two chunks. That run averaged 1.29 target
  stages busy (1.54 during target phases) and spent 84.66 s in draft-only phases. The 3+1 pipeline replaced this design.

## 3. Proposed exact change: take layer 16 off stage0 for prefill

**First form: cuts 0/16/33/48.** Only a contiguous cut moves; per-layer arithmetic, 256-row chunk order, wire and draft
replay are unchanged, and the final owner stays the same. Equal16 passed the canonical proof under the same kind of change:
2,065 target and 73 draft sources, 122,364 pairs, 512 outputs (`equal16-topology-screen/equal16-r1-evidence/summary.json`).

**Estimate.** Stage0 = equal16's measured 233.715 s. Stage1 = 233.046-236.133 s from two cross-run differences (layer 16
costs 14.719 s and layer 32 13.543 s per prefill). Stage2 = control 211.771 s. **TTFT 236.12-238.54 s (-4.9% to -5.9%).**
If decode stays at the control's 10.54 s, the request takes about 246.7-249.1 s.

**Decode risk.** Equal16's decode loss (48.52 to 40.88 tok/s all511) is not stage work: its decode window grew from
10.604 s to 12.593 s while per-stage command time changed by only +0.06, +0.67, +0.31 and +0.06 s (`commands.jsonl.gz`
in both runs). The decode effect of 0/16/33/48 is unknown; the test must measure it.

**Fallback if decode loses: phase-specific cuts (backlog idea 12, new-unmeasured).** Read the prompt on 0/16/32/48
(measured TTFT 236.209 s), then hand the GDN state of layers 16 and 32 to owners on decode cuts 0/17/33/48. That is at
most 9,805,824 B (`screen.json` moves), less than one chunk's stage-to-stage hidden copy (256 x 40,960 = 10,485,760 B),
which prefill already makes 476 times per hop. Derived request: 246.75 s, against 261.38 s (control) and 248.72 s
(equal16). Needs new native code: owners holding both layer ranges, plus a state hand-off command.

**Limits.** Integer cuts cannot go below about 228.6 s; equal16 is already within 2.9% of its own balanced mean
(227.21 s). Both moved layers are GDN, so QSA KV placement and append order are unchanged (four QSA layers per stage).
Activation and transport buffers are unchanged. Stage1 gains layer 16's 1,204,484,316 B: a 24,995,465,228 B projection
(7.22 GB below 30 GiB), ring image +31,421,460 B at depth 3 (accounting, not native admission). Using the draft card's
idle time (all-owner work / 4 = 212.43 s) needs target layers on the draft card, which is not an existing configuration.

**Prior coverage.** No `DO-NOT-REPEAT.md` row under `experiments/own-xpu-runtime` covers prefill cut rebalancing, wider
waves or phase topology (all such files searched). Equal16 is a measured mixed result, not a closed negative. Backlog
idea 1 `single_boundary_followup` lists 0/16/33/48 as unmeasured. Idea 9 "wider waves" applies to PP4 only; in the 3+1
lane it is used up (zero lease waits).

## 4. Smallest device test (existing harnesses only)

1. **Config.** Copy `equal16-topology-screen/control-r1-evidence/control-config.json.gz`; change only `boundaries` to
   [0,16,33,48] and the output path (fresh exclusive root). Keep binary 339b75 (receipt
   `engine-build-reference-route-mtp-20261028-r1`), reference routing, 262K, 256-row chunks, 4 slots, depth 3, cards
   23/27/47 plus draft 43. Not the older `candidate-config.json.gz`, which pins a different build receipt.
2. **Plan.** `engine/tools/pipeline_driver.py` on CPU; read actual planner floors and per-card allocation census first.
3. **Gate.** Existing 3+1/262K 1677-prompt/32-output full-state gate: 2,065 target and 73 draft sources, 1,707 pairs,
   32 outputs (as `reference-one-row/router-tie-candidate/planner-policy/mtp-gate-r1-evidence/`, 328.0 s wall).
4. **Timing.** One first-inference 121,854/512 request against the retained control (TTFT 250.842 s, all511 48.515 tok/s),
   compared with `equal16-topology-screen/compare_reference_long.py`. An arm takes 468.6-482.7 s of owner lifetime
   (equal16/control `terminal.json.gz`). Two retained 3+1 runs on different builds differ by 0.10 s TTFT: 250.742 s
   (`aot-cold-gate/3plus1-262k-long512-r1-evidence/summary.json`) vs 250.842 s. Re-run the control only if the gain is under 1%.
5. **Time and reading.** About 13.3-13.5 min (21.3-21.6 with a matched control). Expect TTFT 236-239 s; keep 0/16/33/48
   for long prompts if decode holds near 48.5 tok/s, else record it and move to the phase-specific fallback.

**Missing evidence.** No GPU event timelines. Native per-chunk `prefill-timings.jsonl` files are empty (OP15 bypasses
that logger), so per-layer stage1/stage2 costs are not retained. Stage0's 31.47 ms per chunk outside the profiled sites is
unattributed. Equal16's decode loss is unexplained. Cuts 0/16/33/48 have no plan, admission or run (TTFT is an estimate).
