# 145-frame continuation budget and the next exact levers

2026-10-10. CPU-only saved-file analysis. The coordinator owns live operations. No GPU, runtime import, launch, check-only, endpoint, device, unit, signal, host-setting change, existing-run write or client-tree write occurred. Analysis used nice 19, OMP_NUM_THREADS=2 and the pinned baseline Python with `-B`.

**The late packet 125 receipts change the diagnosis: GC 60 removed the recurring post-commit two-cycle.** Its remaining even/odd period difference mainly mixes fresh text every fourth chunk with reused text. All 19 remaining long post-commit handoffs overlap recorded manual maintenance. No second unexplained 0.3-second alternating handoff is evident. Packet 126 was absent from the original capture; its later streaming addendum below supplies the measured budget and revised forecast.

## Evidence and definitions

[Read-only analyzer](../data/resume-20261008/continuation127-budget-analysis.py) and [frozen evidence](../data/resume-20261008/continuation127-budget-evidence.json) retain input SHA256/byte counts, capture time, receipt identities, every measured row, timeline examples, maintenance events and matched-window summaries. The analyzer imports the previous packet 125 standard-library file reader without running its entry point. It reads JSON/JSONL regular files only.

```sh
nice -n 19 env OMP_NUM_THREADS=2 /home/steve/.venvs/ltx25-baseline/bin/python -B experiments/ltx25-b70/data/resume-20261008/continuation127-budget-analysis.py
```

Each continuation supplies 144 new frames after dropping the repeated anchor: **6.0 seconds**, not145/24. The 0.90 s/s target needs **≤5.40seconds**. Period means current submit→next submit. Parity below identifies the **source** sequence; the coordinator labels the destination, so their parity is reversed. Fresh text is source `seq % 4 == 0`. Interior rows start at 10 and have complete predecessor/successor evidence. No selected slow row is removed. Snapshot durations are nested inside chain buckets, never added twice. Medians do not add; the script checks the eleven exclusive intervals sum to each individual period within one microsecond.

| Session | Interior intervals | Source range | All median s | Fixed 10→50 median s | Fixed 40 even / odd s |
|---|---:|---|---:|---:|---:|
| s121-live01 | 409 | 10–418 | 5.717 | 5.611 | 5.995 / 5.482 |
| s121-live02 | 305 | 10–314 | 5.757 | 5.620 | 5.962 / 5.484 |
| s123b-legacy-live01 | 50 | 10–59 | 5.828 | 5.828 | 6.255 / 5.679 |
| s123b-live01 | 30 | 10–39 | 5.838 | unavailable | unavailable |
| s123b-live02 | 202 | 10–211 | 5.897 | 5.857 | 6.255 / 5.693 |
| s124-live01 | 34 | 10–43 | 5.846 | unavailable | unavailable |
| s125-live01 | 206 | 10–215 | 5.778 | 5.787 | 6.074 / 5.740 |

The preserved 121 frontier 5.61–5.64 s is a bounded-window result. Full-session medians differ because of the strongly separated parity/text populations, different row counts and a late 121a client pause. Packet 125’s 206 intervals are later than the initial 56-period coordinator summary. These do not erase that earlier observation; direct timestamps clarify its mechanism. Packet 124 only supplies 34 interior intervals. Short 123b aux live01 is retained in JSON and the census; aux live02 appears in the tables below.

## Exclusive chain budget

Every cell is **even-source / odd-source median seconds** over the full interior sample. Different setups are not matched causal placement comparisons.

| Exclusive interval | 121a | 121b | 123b legacy | 123b aux2 | 124 parallel2 | 125 GC 60 |
|---|---:|---:|---:|---:|---:|---:|
| Submit→sampler A: text + A prep | 0.639 / 0.505 | 0.615 / 0.508 | 0.649 / 0.560 | 0.665 / 0.546 | 0.718 / 0.538 | 0.816 / 0.579 |
| Sampler A | 1.914 / 1.909 | 1.909 / 1.906 | 1.922 / 1.927 | 1.926 / 1.914 | 1.902 / 1.891 | 1.922 / 1.919 |
| A done→sampler B: upsample + B prep | 0.322 / 0.320 | 0.328 / 0.327 | 0.334 / 0.348 | 0.341 / 0.341 | 0.311 / 0.314 | 0.340 / 0.335 |
| Sampler B | 1.697 / 1.681 | 1.693 / 1.679 | 1.686 / 1.681 | 1.626 / 1.622 | 1.620 / 1.620 | 1.699 / 1.680 |
| B done→cone video ready, including queue | 0.894 / 0.893 | 0.893 / 0.892 | 0.921 / 0.912 | 1.029 / 1.015 | 0.942 / 0.946 | 0.922 / 0.921 |
| Video ready→durable anchor | 0.030 / 0.030 | 0.030 / 0.030 | 0.034 / 0.031 | 0.031 / 0.031 | 0.033 / 0.031 | 0.031 / 0.030 |
| Anchor→receipt staged | 0.102 / 0.100 | 0.101 / 0.099 | 0.129 / 0.122 | 0.119 / 0.116 | 0.116 / 0.113 | 0.123 / 0.123 |
| Receipt staged→commit mark | 0.005 / 0.005 | 0.005 / 0.005 | 0.031 / 0.030 | 0.034 / 0.033 | 0.028 / 0.028 | 0.034 / 0.036 |
| Commit mark→commit written | 0.013 / 0.008 | 0.008 / 0.010 | 0.015 / 0.015 | 0.015 / 0.015 | 0.015 / 0.015 | 0.015 / 0.015 |
| Commit written→first served | 0.313 / 0.032 | 0.307 / 0.033 | 0.340 / 0.035 | 0.342 / 0.047 | 0.384 / 0.042 | 0.048 / 0.046 |
| First served→next submit | 0.023 / 0.024 | 0.023 / 0.023 | 0.021 / 0.024 | 0.019 / 0.024 | 0.021 / 0.025 | 0.025 / 0.021 |
| Whole period, not sum of medians | 5.945 / 5.526 | 5.910 / 5.547 | 6.133 / 5.689 | 6.144 / 5.706 | 6.056 / 5.571 | 6.044 / 5.724 |

Sampler A+B median is **3.578 s** in 121b fixed 40. Summing exact sampler intervals and dividing by the same total periods gives **62.34%**; 125 fixed 40 is 3.620 s and 61.02%. The 0.90 target requires about 0.21–0.24 s beyond the preserved 121 frontier.

## Off-chain work and worker timelines

These durations overlap the next chunk. Decode tail here is **display_done→record_staged**, including audio where it follows display and CPU hash/record work. The often quoted 0.4 s applies to aux2; legacy is 0.86–0.88 s. Packet 124 moves audio before display and uses a separate completion worker, leaving about 0.13 s post-display. Preview encode/write already has its own bounded worker.

| Work | 121a | 121b | 123b legacy | 123b aux2 | 124 parallel2 | 125 GC 60 |
|---|---:|---:|---:|---:|---:|---:|
| A prep for successor | 0.564 / 0.318 | 0.551 / 0.320 | 0.615 / 0.373 | 0.621 / 0.371 | 0.665 / 0.406 | 0.365 / 0.374 |
| Native A encode bracket | 0.135 / 0.201 | 0.136 / 0.191 | 0.161 / 0.236 | 0.169 / 0.233 | 0.163 / 0.273 | 0.229 / 0.233 |
| Full display decode | 2.821 / 2.840 | 2.844 / 2.850 | 2.866 / 2.861 | 2.839 / 2.838 | 2.700 / 2.693 | 2.854 / 2.863 |
| Display→record staged tail | 0.858 / 0.884 | 0.850 / 0.868 | 0.864 / 0.884 | 0.415 / 0.416 | 0.128 / 0.129 | 0.855 / 0.878 |
| Preview write-start→written | 0.671 / 0.662 | 0.679 / 0.671 | 0.685 / 0.672 | 0.715 / 0.728 | 0.643 / 0.639 | 0.672 / 0.664 |
| Cone queue wait | 0.000 / 0.000 | 0.000 / 0.000 | 0.000 / 0.000 | 0.000 / 0.000 | 0.000 / 0.000 | 0.000 / 0.000 |

The next tables show **actual consecutive examples**, not sums of medians. Each column starts at its chunk’s submit; negative offsets precede it. Decode/preview rows belong to the predecessor feeding or overlapping this prompt. Own A prep feeds the successor. JSON retains four examples(10–13) per session, including both121 runs and both123b placements.

### s121-live02

| Worker/event, relative seconds | seq 10 even | seq 11 odd |
|---|---:|---:|
| Prompt request-before snapshot | 0.041–0.103 | 0.070–0.130 |
| Prompt A-before snapshot | 0.256–0.311 | 0.283–0.342 |
| Prompt A-after snapshot | 0.366–0.423 | 0.396–0.450 |
| Prompt sampler A | 0.455–2.354 | 0.477–2.367 |
| Prompt B-before snapshot | 2.443–2.498 | 2.480–2.539 |
| Prompt B-after snapshot | 2.566–2.622 | 2.606–2.661 |
| Prompt sampler B | 2.646–4.315 | 2.686–4.366 |
| Decode current cone on chain | 4.315–5.199 | 4.366–5.266 |
| Prompt request-after snapshot | 5.265–5.323 | 5.344–5.408 |
| Prompt staged→executor exit | 5.323–5.348 | 5.408–5.434 |
| HTTP commit written→served | 5.342–5.639 | 5.428–5.460 |
| HTTP next submit | 5.663–5.663 | 5.486–5.486 |
| Decode predecessor A prep | -0.110–0.187 | -0.315–0.224 |
| Decode predecessor B prep | 0.455–0.602 | 0.478–0.627 |
| Decode predecessor display | 0.602–3.310 | 0.627–3.436 |
| Decode predecessor display→record | 3.310–4.236 | 3.436–4.278 |
| Preview predecessor encode/write | 4.307–4.961 | 4.343–5.035 |
| Decode current successor A prep | 5.348–5.887 | 5.434–5.743 |

### s123b-legacy-live01

| Worker/event, relative seconds | seq 10 even | seq 11 odd |
|---|---:|---:|
| Prompt request-before snapshot | 0.162–0.232 | 0.101–0.167 |
| Prompt A-before snapshot | 0.391–0.453 | 0.326–0.386 |
| Prompt A-after snapshot | 0.512–0.575 | 0.443–0.504 |
| Prompt sampler A | 0.604–2.541 | 0.532–2.468 |
| Prompt B-before snapshot | 2.651–2.718 | 2.559–2.619 |
| Prompt B-after snapshot | 2.798–2.869 | 2.689–2.747 |
| Prompt sampler B | 2.901–4.585 | 2.773–4.454 |
| Decode current cone on chain | 4.585–5.491 | 4.454–5.363 |
| Prompt request-after snapshot | 5.572–5.643 | 5.438–5.505 |
| Prompt staged→executor exit | 5.643–5.686 | 5.505–5.553 |
| HTTP commit written→served | 5.679–6.013 | 5.547–5.569 |
| HTTP next submit | 6.038–6.038 | 5.592–5.592 |
| Decode predecessor A prep | -0.037–0.325 | -0.351–0.263 |
| Decode predecessor B prep | 0.604–0.774 | 0.532–0.714 |
| Decode predecessor display | 0.774–3.689 | 0.714–3.462 |
| Decode predecessor display→record | 3.689–4.512 | 3.462–4.375 |
| Preview predecessor encode/write | 4.582–5.260 | 4.442–5.109 |
| Decode current successor A prep | 5.686–6.301 | 5.553–5.907 |

### s124-live01

| Worker/event, relative seconds | seq 10 even | seq 11 odd |
|---|---:|---:|
| Prompt request-before snapshot | 0.225–0.305 | 0.094–0.166 |
| Prompt A-before snapshot | 0.477–0.548 | 0.322–0.383 |
| Prompt A-after snapshot | 0.620–0.690 | 0.441–0.502 |
| Prompt sampler A | 0.718–2.633 | 0.530–2.418 |
| Prompt B-before snapshot | 2.723–2.783 | 2.515–2.575 |
| Prompt B-after snapshot | 2.851–2.910 | 2.649–2.713 |
| Prompt sampler B | 2.934–4.553 | 2.738–4.361 |
| Decode current cone on chain | 4.553–5.494 | 4.361–5.308 |
| Prompt request-after snapshot | 5.563–5.632 | 5.380–5.450 |
| Prompt staged→executor exit | 5.633–5.674 | 5.450–5.498 |
| HTTP commit written→served | 5.667–6.033 | 5.489–5.517 |
| HTTP next submit | 6.056–6.056 | 5.534–5.534 |
| Decode predecessor A prep | -0.035–0.412 | -0.382–0.256 |
| Decode predecessor B prep | 0.719–0.871 | 0.530–0.673 |
| Decode predecessor display | 1.195–3.890 | 0.991–3.683 |
| Decode predecessor display→record | 3.890–4.021 | 3.683–3.814 |
| Preview predecessor encode/write | 4.100–4.721 | 3.890–4.546 |
| Decode current successor A prep | 5.674–6.312 | 5.498–5.906 |

### s125-live01

| Worker/event, relative seconds | seq 10 even | seq 11 odd |
|---|---:|---:|
| Prompt request-before snapshot | 0.126–0.196 | 0.133–0.199 |
| Prompt A-before snapshot | 0.360–0.420 | 0.359–0.422 |
| Prompt A-after snapshot | 0.477–0.549 | 0.480–0.541 |
| Prompt sampler A | 0.579–2.510 | 0.569–2.500 |
| Prompt B-before snapshot | 2.605–2.673 | 2.616–2.682 |
| Prompt B-after snapshot | 2.752–2.817 | 2.765–2.832 |
| Prompt sampler B | 2.849–4.545 | 2.863–4.542 |
| Decode current cone on chain | 4.545–5.457 | 4.542–5.463 |
| Prompt request-after snapshot | 5.531–5.611 | 5.536–5.608 |
| Prompt staged→executor exit | 5.612–5.652 | 5.608–5.653 |
| HTTP commit written→served | 5.645–5.688 | 5.644–5.670 |
| HTTP next submit | 5.720–5.720 | 5.687–5.687 |
| Decode predecessor A prep | -0.063–0.287 | -0.067–0.294 |
| Decode predecessor B prep | 0.580–0.735 | 0.569–0.718 |
| Decode predecessor display | 0.735–3.545 | 0.718–3.641 |
| Decode predecessor display→record | 3.545–4.463 | 3.641–4.477 |
| Preview predecessor encode/write | 4.528–5.220 | 4.532–5.252 |
| Decode current successor A prep | 5.652–6.013 | 5.653–6.024 |

## GC 60 removed the recurring handoff; fresh text explains most remaining parity

Packet 125 has 206 interior intervals and 19 commit-written→first-served waits>150 ms. **All 19 overlap measured manual maintenance**; none of the other 187 does. Across 23 retained maintenance events, including qualification/startup, median GC is **0.254 s**, cache housekeeping **0.056 s**. These are recorded callbacks, not a fitted automatic-GC hypothesis.

| Session / source modulo 4 | 0 fresh text | 1 reused | 2 reused | 3 reused |
|---|---:|---:|---:|---:|
| s121-live02 period | 6.253 | 5.560 | 5.783 | 5.534 |
| s121-live02 submit→A | 0.931 | 0.505 | 0.518 | 0.509 |
| s121-live02 commit→serve | 0.307 | 0.034 | 0.307 | 0.032 |
| s123b-legacy-live01 period | 6.447 | 5.674 | 6.020 | 5.707 |
| s123b-legacy-live01 submit→A | 0.984 | 0.560 | 0.612 | 0.560 |
| s123b-legacy-live01 commit→serve | 0.336 | 0.031 | 0.341 | 0.044 |
| s125-live01 period | 6.191 | 5.706 | 5.756 | 5.725 |
| s125-live01 submit→A | 1.004 | 0.576 | 0.590 | 0.583 |
| s125-live01 commit→serve | 0.050 | 0.045 | 0.047 | 0.047 |

Excluding only maintenance-overlapping handoffs as a separately labeled diagnostic, 125 class medians are **6.183 /5.702 /5.741 /5.717 s**. Reused class 2 differs from classes1/3 by24–38 ms, not0.3–0.4 s. Fresh class 0 retains about 0.43 s extra submit→A work. Pooling class 0 with class 2 creates a misleading “even” median between populations. Future gates must stratify modulo 4 and maintenance overlap.

No alternate-chunk FIFO wait appears: median queue waits are tens of microseconds. Request-before snapshots have no sustained alternating pause; predecessor display begins after them in the examples. Every analyzed A source is precomputed. The bounded go wait ends at successor sampler A and follows admission; it is not proof that display blocked cone. Predecessor preview normally finishes before current receipt.

## Six safety snapshots and safe sharing

At 121b fixed 40, medians of summed parts per chunk are **state 0.176 s, facts 0.151 s, residence 0.018 s, memory 0.006 s**. Six ordinary snapshots cost roughly 0.35–0.37 s. The historical0.057 s each is not universal:125 fixed 40 parts are **0.206 /0.166 /0.026 /0.006 s**, with full sum about 0.40 s. Periodic duals and near-floor fallbacks remain included. Outer synchronization time is not part of these inner timers.

| Snapshot, all 125 median seconds | Even-source | Odd-source |
|---|---:|---:|
| request-before | 0.071 | 0.069 |
| A-before | 0.066 | 0.064 |
| A-after | 0.064 | 0.063 |
| B-before | 0.066 | 0.064 |
| B-after | 0.065 | 0.064 |
| request-after | 0.071 | 0.072 |

**Do not cache state or tensor facts across snapshots.** Sealed `snapshot_fingerprint.py` re-enumerates parameter/buffer registrations and rereads tensor identity, storage pointer, shape, dtype and device every time. `Tensor.data`, `set_`, `resize_`, tensor swaps and direct registration changes can bypass Python placement-event/version caches. State also checks current phase, routes, faults, owner/registry and text/decoder state. “Unchanged this chunk” is not proven.

The safe narrower lever is a **pure digest memo keyed by the complete freshly read immutable signature**. All reads/checks remain at every boundary; equal complete keys imply equal canonical digest bytes. It removes repeated serialization/hash work, not state/fact observations. Packet 127’s launch-selectable parent-off form, bounded cache, mutation tests and CPU replay are recorded in its [design](2026-10-10-continuation127-stream-design.md). No native saving is established by a CPU timing.

## Sampler bound and current graphs

The “three quarters CPU dispatch” result in the September 14
`dispatch-bound-diagnosis-01.md` is packet 12's **eager 25-frame** path.
The September 15 `real-block-timing-01.md` graph profile measured **81.5%
blocks / 18.5% orchestration and nonblock work**, also at 25 frames. Neither is
a current 145-frame profile. Large isolated GEMMs were near the copy roofline;
small projections remained inefficient. Thus “GEMM-roofline bound” and “CPU
dispatch bound” describe different observations and must not be collapsed into
a claim that 75% of today's sampler time is removable.

In sealed parent 126, `source/scripts/ltx_graph_capture.py` builds immutable
argument-description keys in `key_for` (line 420). `_call_native` (1210–1260)
still runs eager `_validate_fast`, registry/slot/key lookup, per-forward
`_validate`, `group.fill` input copies and locking, then calls each block's
`graph.replay`. `candidate_safety.py` (69, 77) pins all 48 blocks and chain length
one. The archived 121-at-145 `graph-capture-qgraph-c2.json` confirms **192
captures = 48 routes × 4 signatures**; 8 + 3 sampler steps mean **528 block
replays per chunk**. Model preparation/output, sampler updates, argument movement
and the outer Python loops remain eager. A larger graph must preserve the
mutable input and route checks and fit its extra persistent storage.

Two-way 20/28 is **sequential layer sharding**: blocks 0–19 on xpu:0, then
20–47 on xpu:1, with final activations returned to the primary. One card waits
because of dependencies; the split is memory packing, not two concurrent stages
whose maximum duration defines the sampler. A 24/24 split adds about **2.88 GiB**
of resident weights on xpu:0 against its measured **1.27–1.4 GiB** margin; even
23/25 adds 2.16 GiB. Receipts provide no per-card block times or speed benefit
that would justify this memory loss. Redividing the same sequential sum is not
a demonstrated exact lever.

Text layers split 24/24 on xpu:2/3, with 480 graphs captured during preparation.
The existing reuse path binds the prompt hash and cached tensor hashes; changed
prompts really encode, and qualification checks raw bytes. There is no unused
whole text encode on a reused-text chunk to eliminate. Reusing a changed
prompt's previous model output would cross the no-reuse benchmark boundary.
Pure signature-digest memoization does not reuse model computation.

The packet 127 memo's source-shaped CPU experiment performs 288 digests per
six-snapshot batch, over four keys per route and 6,827-byte representations.
Across 50 paired batches, parent median is **0.051773 s**, memo median
**0.000541 s**, saving **0.051233 s**. These are synthetic keys shaped like the
source, not captured current-runtime keys; they support a provisional native
saving of **0.03–0.07 s**, not a measured model speed. Fresh reads and all checks
remain required. Full CPU equivalence counts are in the packet design/build.

## Ranked exact levers

Savings below are **estimates** except explicitly observed historical durations. They are not additive guarantees; CPU contention and critical-path movement overlap.

| Rank / lever | Estimated opportunity | Exactness / memory | Risk and disposition |
|---|---|---|---|
| 1. Packet 126 background fix + inherited GC 60| 126 CPU replay saves ~0.144 s plan checks. GC 60 removes ~0.29 s from most formerly slow handoffs, roughly 0.10–0.15 s mean opportunity before overlap. Latest 126 evidence supports a first 127 forecast including memo of 5.45–5.70 s (0.908–0.950 s/s), unmeasured; see addendum.|Reserve/mutation checks retained; GC still runs. No arithmetic change; longer retained allocator storage must pass floors.|Most supported immediate arm. Do not subtract both estimates from pooled medians and promise ≤0.90.|
| 2. Packet 127 pure signature-digest memo with fresh reads|Bounded by ~0.18–0.21 s state work; only serialization/hash portion removable. Source-shaped CPU replay saves 0.051233 s; provisional native opportunity 0.03–0.07 s.|Every mutable fact reread, same checks; bounded small host cache, no graph pool.|Default parent-off; exact digest/mutation tests. CPU savings are not native timing.|
| 3. 169 frames with 124 parallel display2 + early audio after 126|Prior forecast 6.20–6.65 s / 7 s = 0.886–0.950 s/s. Packet 126 may improve it, but additive subtraction is unmeasured.|Unchanged target schedule/precision; native byte gates. Prior projected margins 1.34/1.80/2.21/1.81 GiB.|Could cross 0.90 without cone graph; this combination at 169 remains unmeasured.|
| 4. 145-frame cone under decoder graph|121-frame graph cone ~0.77 s versus 145 eager ~0.89–1.03 suggests 0.10–0.25 s, cross-shape estimate.|Same operations require byte gates; first 121 capture 3,430,940,672 bytes(3.20 GiB) retained versus 145 legacy xpu:3 margin 1.85 GiB.|Positive cap checks prior growth (initially 0); cap below first capture growth does not prevent first capture. No proven safe positive cap.|
| 5. Cone graph on xpu:2 beside display replica|Similar theoretical 0.10–0.25 s, less transfer/queue cost.|Could share decoder weights, but graph pool + display transient + text must fit and compare byte-for-byte.|Current display replica is eager. Its conservative 145-frame budget is 9.705818 GiB headroom − 0.776972 GiB weights − 5.640625 GiB display reserve − 0.75 GiB safety allowance = **2.538221 GiB**, below the 121-frame graph pool of 3.195 GiB before any longer-shape growth. These are planning reserves, not proof that actual simultaneous allocations cannot fit. New owner/locks/admission and cross-card byte gates needed; no proven fit.|
| 6. Sampler eager residue/split balance|Even 5% sampler is ~0.18 s; receipts do not prove 5% removable.|Keep arithmetic, shape, route and oracle gates; larger graphs retain storage.|Measure eager pieces/per-card stalls first. Sequential split balancing may merely move work and alter bytes.|
|Closed: cross-snapshot state/fact caching|Nominal ~0.33–0.37 s parts tempting, not valid savings.|Can miss storage/device/registration mutations.|Rejected; fresh-key digest cache is narrower.|
|Closed: another 0.3 s two-cycle / new preview worker|No supported unexplained alternating handoff after GC 60.|Fresh text retained; preview worker already exists.|Parity mixture is not a new mechanism.|

Open: packet 127 native byte/memory/timing gates; safe 145 first-capture cone bound; per-card sampler stalls/current 145 graph-residue profile. The coordinator controls every live action.

## Later read-only packet 126 availability check

At 2026-10-10T08:29:37.857815+00:00, the client directory
`/home/steve/ltx-stream/s126-live01` exists, but its `manifest.jsonl` does not.
The server run directory
`encoder-server-continuation-stream-126-frame-dg0-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f145-ssbackground`
contains five qualification receipts and **zero streaming receipts**.
Thus packet 126 is being qualified; no streaming budget can yet be derived.
This later observation does not replace the original seven-session frozen capture.
The final source-shaped digest CPU numbers above are preserved in
[the CPU benchmark](../data/resume-20261008/continuation127-signature-cpu.json)
and its [reproduction script](../data/resume-20261008/continuation127-signature-cpu.py).

## Packet 126 streaming addendum: the current forecast moves to 5.45–5.70 s

This supersedes the availability-only check above. At **2026-10-10T08:43:35.238543+00:00** packet 126 had **138 completed manifest rows**, yielding **127 interior intervals**, source sequences **10–136**. The [separate frozen126 evidence](../data/resume-20261008/continuation127-126-budget.json) and [exclusive-output analyzer](../data/resume-20261008/continuation127-126-budget-analysis.py) preserve this later capture without changing the original seven-session evidence. All 127 exclusive chain sums close within one microsecond. Source identities confirm 145 frames, legacy auxiliaries, serial display on xpu:3, storage background, GC 10.

Its full-interior median is **5.7017 s (0.9503 s/s)**. The fixed 40 median is **5.7216 s**, matching the coordinator’s roughly 5.722 s report despite the later full capture. Fixed 40 even-source/odd-source medians are **6.0478 /5.5881 s**. The preserved 121 fixed 40 frontier remains 5.61–5.64 s; 126 removes identified bookkeeping work but has not established a return to that frontier.

| Exclusive interval, median seconds | 126 even-source| 126 odd-source| 126 fixed 40 all| 123b legacy fixed 40 all|
|---|---:|---:|---:|---:|
|Submit→A: text + A prep|0.6811|0.5004|0.5206|0.5922|
|Sampler A|1.9320|1.9377|1.9361|1.9216|
|Upsample + B prep|0.3227|0.3178|0.3189|0.3398|
|Sampler B|1.7086|1.6799|1.6963|1.6833|
|B done→cone video ready|0.9293|0.9267|0.9278|0.9178|
|Video ready→anchor|0.0298|0.0302|0.0289|0.0319|
|Anchor→receipt staged|0.0930|0.0939|0.0957|0.1224|
|Receipt staged→commit mark|0.0035|0.0034|0.0033|0.0295|
|Commit write|0.0131|0.0131|0.0132|0.0154|
|Commit written→first served|0.3222|0.0394|0.1822|0.1849|
|Served→next submit|0.0174|0.0271|0.0180|0.0223|
|Whole period|6.1033|5.5682|5.7216|5.8284|

In the matched 40 window, period medians fall5.8284→5.7216 s, while **mean period falls 126.2 ms**. Means of exclusive intervals are additive; unrelated medians are not. Sampler timings and other work can offset some CPU improvement. This does not isolate a native0.144-second gain from the earlier CPU replay.

| Off-chain work / snapshot sum, median seconds | 126 even-source| 126 odd-source|
|---|---:|---:|
|Successor A preparation|0.5725|0.3191|
|Native A encode bracket|0.0441|0.1876|
|Display decode|2.8803|2.8952|
|Display→record staged tail|0.8181|0.8398|
|Preview encode/write|0.6896|0.6785|
|Cone FIFO wait|0.0001|0.0001|
|Six snapshot sum, already inside chain|0.3669|0.3716|

### Packet 126 consecutive thread timelines

Seconds relative to each chunk’s submit. Decode/preview predecessor work overlaps this prompt. These are observed intervals, not synthetic median sums.

|Worker/event|seq 10 even|seq 11 odd|
|---|---:|---:|
|Prompt request-before snapshot|0.034–0.129|0.031–0.108|
|Prompt A-before snapshot|0.349–0.407|0.313–0.367|
|Prompt A-after snapshot|0.458–0.514|0.421–0.476|
|Prompt sampler A|0.551–2.470|0.500–2.420|
|Prompt B-before snapshot|2.574–2.627|2.526–2.581|
|Prompt B-after snapshot|2.700–2.753|2.654–2.709|
|Prompt sampler B|2.779–4.482|2.735–4.415|
|Decode cone on chain|4.482–5.389|4.415–5.338|
|Prompt request-after snapshot|5.468–5.524|5.416–5.474|
|Prompt staged→executor exit|5.524–5.540|5.474–5.495|
|HTTP commit written→served|5.535–5.842|5.492–5.497|
|HTTP next submit|5.852–5.852|5.506–5.506|
|Decode predecessor A prep|-0.010–0.302|-0.312–0.247|
|Decode predecessor B prep|0.551–0.711|0.501–0.667|
|Decode predecessor display|0.711–3.588|0.667–3.537|
|Decode predecessor display→record|3.588–4.401|3.537–4.352|
|Preview predecessor encode/write|4.473–5.151|4.428–5.107|
|Decode current successor A prep|5.540–6.099|5.495–5.814|

### Revised forecast and interpretation

All **64** packet 126 commit→serve gaps over 150 ms overlap measured manual GC 10. Modulo 4 gives:

|Source class|0 fresh|1 reuse|2 reuse|3 reuse|
|---|---:|---:|---:|---:|
|Period|6.3203|5.5763|5.8554|5.5611|
|Submit→A|0.9465|0.5020|0.5199|0.4948|
|Commit→serve|0.3222|0.0430|0.3222|0.0331|

The remaining126 slow handoff is therefore directly measured GC 10, while125GC 60 already demonstrated that this recurring gap can disappear. Yet125’s aggregate result was neutral because fresh-text and other path costs remained. Combining126+GC 60+the digest memo has no matched native run.

A deliberately simple **counterfactual**, not a performance measurement, replaces each126 commit→serve excess above40 ms with40 ms. Its median becomes5.5936 s; subtracting an illustrative50 ms digest saving gives5.5436 s. It omits infrequent retained GC, changes in scheduling/allocator behavior and workload interactions. It is useful only as a budget cross-check.

The recommended 127 first-arm forecast is now **5.45–5.70 s per 6.0 s of new video (0.908–0.950 s/s)**, with a working target near **5.55 s /0.925 s/s**. This is more conservative than promising 0.90. The target 5.40 s still requires roughly 0.15 s beyond that midpoint, so the ranked 169/display2 and genuinely safe cone-graph or sampler-residue work remain relevant. Preserve full matched 40, modulo 4, direct maintenance overlap and native byte/memory gates when the coordinator evaluates127.

The display-reserve arithmetic above uses the sealed parent 126
`stream_contract.display_transient_bytes(145)` formula:
`4 GiB × (19/16)^2 = 5.640625 GiB`. The prior 145 census gives
`11.705818 − 2 = 9.705818 GiB` headroom on xpu:2. Replica checkpoint
bytes are **834,267,746**, or **0.776972 GiB**, from the
[145 census](2026-10-10-continuation121-results-145.md). Subtracting
those costs and the stated 0.75 GiB planning allowance leaves **2.538221 GiB**.
The allowance is a conservative screen, not an extra measured allocation.
