# Packet183: two-card S1 dense-scales one-load bracket (lane B), with a prepared win-path waiter

CPU preparation only. No GPU, `/dev/dri`, service, setting, PAUSE file or live queue was touched,
and nothing was queued. Unsloth UD-IQ3_XXS of Qwen3.8 Flash-Next (the quantized compressed
version), two B70 cards, single user, greedy, 128-token capped suite, exact against
`iq3-p49-split32-v1`, full BF16 KV and state. The record it targets is the two-card
**58.798109 tok/s** (packet136 bundle 8, LocalMaxxing `cmve4dtir007wrf01k57sdf23`).

This is resume-queue item (a) of the 2026-10-19 owner pause ("packet178 S1 dense-scales micro,
lane B"). It **supersedes that stopped prep**: the untracked `stage2/packet178-twocard-s1-micro/`
named in CURRENT.md no longer exists on this host (not on disk, not in git, not in any stash;
it was most likely removed with the 2026-10-19 untracked-file cleanup), and the name packet178
now belongs to the committed one-card portable packet. Nothing from it could be reused.

## Which line, and why

The packet177 plan's first step was a one-card kill micro on packet175's harness. This packet
goes straight to the **two-card one-load v5 bracket on the bundle-8 record line** instead:

- S1a changes no storage: every expanded Q6_K row already carries the retained metadata, so the
  switch is kernel-only and fits a one-load A/B/A/B/A bracket (the method that measured 0.057%
  control drift for packet153 on this exact line).
- The bracket measures the whole interval (pipeline overlap, head, draft) under the real
  execution context, which a layer micro cannot, and its device cost is ~12 min of lane B
  (packet153: smoke 3 min + bracket 8 min 14 s) against ~2 min for the micro plus a later bracket.
- Base: an identity-rewritten copy of packet153 (`copy_packet183.py`, receipt
  `lineage/packet183-copy.json`): packet136's banked bundle 8 with packet150's vendored one-load
  harness. Packet153's lane-B bracket ran on device 2026-10-19 01:45-01:53 UTC (controls
  58.638/58.671/58.663 tok/s, 13/13 exact per view); its control selection is bundle 8.

## The lever (packet177 PLAN section 5, "S1 metadata-scale dense lane")

An expanded Q6_K row is `K` int8 codes, `K/16` FP32 scale words, then per 256 weights the
retained 18 bytes of the original block (fp16 `d`, 16 int8 sub-scales). The production lanes read
the 64 bytes of scale words per 256 weights; S1 reads the 18 retained bytes and recomputes
`half(d) * float(signed8(sc))`. Fetched bytes per 256 weights drop from 320 to 274 (**-14.375%**).

**Exact by construction for every finite d.** That expression is the loader's own single FP32
product (`packet10-kopt5/expanded.hpp`), `iq3::half` is the loader's integer-only conversion, and
an 11-bit significand times an integer of magnitude <= 128 is exactly representable in FP32 (no
rounding, no subnormal result, signed zero by sign rule, no add to contract). A non-finite `d`
could differ in NaN sign or payload, so the engine runs a **load-time census** over every Q6_K
expanded tensor (both ranks, both arms, one load): any non-finite `d` or any stored word that
differs from the recomputed product is a sticky startup refusal
(`dense-scales-census.json` in each rank's output).

**Sites (measured at production shape, `v5/evidence/full-shape.json`).** One selection key,
`dense_scales: expanded|metadata`, switches at prepare time:

| Rank | Converted issue sites (per token) |
| --- | --- |
| 0 | attention projection 24 (p49c), gdn.qkv 17, gdn.z 17, qsa.qgate 6 (p33 segment), small.ffn.q6 shared gate/up 23 (p49d) = 87 |
| 1 | attention 24, gdn.qkv 18, gdn.z 18, qsa.qgate 6, small.ffn.q6 24, **target head prefix** (202,240 rows) 1 = 91; **draft head** (80,128 rows) 1 of 59 draft commands |

Not converted (unchanged in both arms): qsa.k/v/iq/ik (p28 rows4, latency-bound), the rank-0
head suffix (a graph captured once in `p105::Runtime`), HC and other Q8 kernels, experts.
Every other command is byte-identical between the two selections (operation bytes and bindings).

## What changed vs the parent

| Item | Change |
| --- | --- |
| Device engine `v5/build/device/own-rt-iq3` | **`36e476d198fb302124fb687c8405cfdcd873d14dff89d94049581ef7c86fc631`** (gnu-host `1164a9eb...`). The 78 packet136 parent objects are linked **unchanged** (pins verified). Recompiled: `entry-main` (v5 `main.cpp`: census + 3 dispatch sites; `mtp.hpp`: draft-head site; `engine_bracket.hpp`: switch key/domains) and `p49d_submit` (`dense_scales` registered: 14 choice keys). New TU `s1_submit` |
| New native files | `native-base/.../s1_lanes.hpp` (metadata scale, three lane copies, census), `s1_kernels.hpp` (`SegKernel`, `SegFinish`, `AttnKernel`, `SmallKernel`: copies of p33/p49c/p49d structs with only the Q6 lane call changed), `s1_submit.{hpp,cpp}` (production validations/bindings). No existing header changed, so no definition is shared under one name with the inherited objects |
| Selections | `v5/lineage/production` (bundle 8 + `dense_scales: expanded`) and `v5/lineage/metadata` (+ `metadata`); `snapshot_host` fixed to `production` |
| Harness | packet153 v5 retargeted (`apply_harness_delta.py`, `harness-delta.patch`); snapshot-only gates removed; S1 gates added; decision rule `v5/s1_decision.py` |
| Delta records | `s1-delta.patch` (466 lines), `lineage/s1-delta.json`, `lineage/packet183-copy-amendments.json` (one vendored module located its packet by name) |

## Expected gain (`v5/evidence/expected-gain.json`, `v5/price_s1.py`)

Recorded inputs only: packet110 roofline (measured per-class device time and runtime weight bytes),
packet160's interval reconstruction of the record (hit 14.704 ms x 932, miss 25.613 ms x 256,
A 12.482, B 13.086, D 1.597 ms), the 590 GB/s measured streaming-read ceiling, the R5 head
efficiency (63%), and the measured site counts above.

| Scenario | Saved per rank (ms) | Pooled interval | Expected |
| --- | --- | --- | --- |
| floor: only the removed bytes' time at 590 GB/s disappears | rank0 0.413, rank1 0.584 (head 0.158), draft 0.062 | 17.055 -> 16.333 ms | **+4.42% (~61.40 tok/s)** |
| proportional: S1 keeps each kernel's achieved bandwidth | rank0 0.537, rank1 0.804, draft 0.099 | 16.058 ms | +6.21% (~62.45 tok/s) |

+2% needs **46%** of the floor saving. Packet177 priced +3.7% without the target and draft
heads. Risks on record: packet175b D1 (same-byte scale-path change in this lane, dense B/A
1.0665), packet74 (per-weight unpack cost more than its bytes; S1 has none), packet175 D2
(L2-warm GEMVs only 15%/5.5% faster, so not purely DRAM-bound). The bracket decides.

## Arms (one load, one process pair, v5)

| Row | Views | Requests |
| --- | --- | --- |
| smoke `packet183-s1-smoke-B` | metadata | incident64 + 12 x 64 tokens, exact, first-request timing proof |
| bracket `packet183-s1-bracket-B` (depends on the smoke) | expanded / metadata / expanded / metadata / expanded | per view incident64 + 12 cold x 128 tokens; 13/13 exact, identical draft proposals, loaded arena identical |

Decision (`v5/s1_decision.py`, recorded as `s1_decision` in the summary): **screen winner** = both
metadata views >= +0.5% over every control, drift <= 3%. **Chain rule** = both >= +2% over every
control AND >= 1.02 x 58.798109 = 59.974 tok/s.

## Rows and wall clock (`ops/lane-queue/proposed-p183-two-card-B.txt`, sha256 `050ccdd8...`)

| Row | Expected | Plan range | Watchdog | Writes |
| --- | --- | --- | --- | --- |
| `packet183-s1-smoke-B` | ~3 min (packet153 smoke 01:40-01:43 UTC) | 240-360 s | 3600 s | 240 MB |
| `packet183-s1-bracket-B` | ~8.5 min (packet153 bracket 8 min 14 s) | 480-900 s | 3600 s | 1.2 GB |
| win path only: `screen-packet183-s1-confirm-A` (waiter) | ~8.5 min | 480-900 s | 3600 s | 1.2 GB |

## Two-card admission needs

- **Cards:** lane B = cards 2+3 (PCI `0000:43:00.0` + `0000:47:00.0`). All three owner endpoints
  must be stopped (vision on cards 1+2, `fp8-tp1-test` on card 3, `fp8` on card 0 for the
  whole-host memory bound), only after `lanequeue.py plan --lane B` passes on a private copy.
  Card 2 has a recorded GuC lockup history; the same rows run unchanged on lane A (cards 0+1;
  `entry_gate` rehearsed both lanes) if the operator prefers.
- **Host RAM:** MemAvailable >= 105,411,248,128 B (97 GiB + 1200 MiB) + the queue's 1 GiB at START
  (windows on 2026-10-22 measured 120.6-120.7 GB with endpoints stopped).
- **PAUSE-A stays during the whole window** (two-card resident rows and the waiter are whole-host).
- Root free >= 25 GB + planned writes (now ~35 GB). No setting changes.

## Gates (all CPU; receipts in `v5/evidence/`)

| Gate | Result |
| --- | --- |
| Build (`p183_v5_build_engine.py`) | both modes, 0 warnings, 78 parent objects pin-verified, ~70 s |
| S1 bytes (`s1_byte_gate.py`, `native/s1_bytes.cpp`) | GNU + Intel, two fresh runs each, identical transcripts: 173,056 lane checks, 80 submission comparisons (p33 segment K2560/6144/10240 v6/v7, p49c attention rows 2560 batch 1/2, p49d tuple; 8 control/input scenarios incl. NaN/inf/subnormal inputs, inactive/error/out-of-range positions), 18 mutation proofs (zeroed FP32 words change production only; bumped sub-scales change S1 only), census negatives (inf and NaN `d` counted, flipped word counted, non-256 K refused) |
| Real-weight census (`real_census_gate.py`) | all 249 expanded Q6_K tensors of the real model (token_embd excluded: lookup): 213,852,160 groups, **0 non-finite d, 0 word mismatches**, 1,118,400 real-row lane checks bit-identical; 3.33 GB read once, ~18 s |
| Production shape (`p183_v5_full_shape.py`) | real v5 `main.cpp`/`mtp.hpp` at production shape, numerical addresses, no payload: both ranks, both orientations (start expanded / start metadata), 5 views each, reset extents, arena identity, 14 native refusals, control captures == fresh startup, metadata captures differ only at mapped S1 sites with identical bindings; real-parser startup of both selections on both ranks |
| Expected gain (`price_s1.py`) | +4.42% floor / +6.21% proportional |
| Controller, switch (mini engine C/X/C/X/C, GNU/Intel), admission (identical plans, 0 new bytes), analysis (incl. `test_s1_decision.py` on packet153's REAL bracket summary: +0.35% -> not a winner), submission rehearsal, safety, exec limits, loader | pass |
| Seal (`cpu_seal.py`), `package_rows.py` | `v5/cpu-seal.json` `2378b030...`; proposal written |
| `check_queue_rows.py` | entry (both lanes, both rows), launch limits, worker (78 requests), report (both lanes), private-copy `lanequeue.py plan --lane B` (both rows passed), `rehearse_entry.py --report` (0 identity refusals), live pin guard, waiter rehearsal |
| `final_checks.py` (+ `--ready`) | all receipts; drain scan (below); READY written last, live pin guard re-run on the full closure, direct classification: 0 cross-packet mutable pins (`v5/evidence/final-pin-guard.json`) |

Drain fix (`scripts/check_drain_fix.py`): the packet's runtime drain code (`v5/conditions.py`,
`v5/p183_v5_drain_gate.py`, `drain_gate.py`) is FIXED; the scan exits 1 only because of two
vendored historical copies under `lineage-inputs/vendor/.../screen/v4-lanes/` that nothing
imports (import trace of the real bracket entry recorded in `final-checks.json`). The queue's
61 s drain spacing and the waiter's spacing wait apply.

## Win path (prepared, NOT armed): `chain/`

`chain/p183_win.py` (entry `chain/p183-win.sh`, arming `chain/ARMING.md`) mirrors packet182's
guarded waiter: it waits for the bracket's terminal event, applies the same decision rule, refuses
while any owner endpoint is active, and never deletes a PAUSE file (saves, holds, restores). There
is no derivable two-card record chain (that is a record bundle: packet136 + `dense_scales`, the next
packet), so on a chain-rule win it launches only the **lane-A confirmation bracket** of this packet
on cards 0+1 through the queue's own command builder. Dry-run rehearsal
(`chain/rehearse_waiter.py`, `v5/evidence/waiter-rehearsal.json`): win case against the real
repository (job validated, 1,077 pins allowed, lane-A `--plan` passed, exact command built,
nothing written to the packet), below-bar, FAILED, SKIPPED-DEPENDENCY, existing output, queue
drift, live endpoints (exit 5) and the PAUSE hold/restore test all pass.

## Not claimed

No device result, speed, exactness on device or record. The expected gain is arithmetic on
recorded measurements. The census proves the loaded bytes and the host arithmetic; device
equality is proven only by the bracket's 13/13 exact views. The lane-B bracket is a screen; a
record needs the fresh-process record chain of a future bundle. No full512/strict512 gate. The
production-shape gate mocks payloads and device addresses; it is not a device run.

[Note](../../../../notes/2026-10-22-packet183-twocard-s1-micro.md) ·
[DO-NOT-REPEAT](DO-NOT-REPEAT.md) · [Retention](RETENTION.md) · [Arming](chain/ARMING.md)
