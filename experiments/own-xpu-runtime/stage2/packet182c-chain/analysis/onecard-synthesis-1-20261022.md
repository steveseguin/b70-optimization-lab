# One-card lever synthesis 1: after the packet182c record (2026-10-22, CPU-only, read-only on the repo)

**Line:** Qwen3.8 Flash-Next UD-IQ3_XXS, own Xe runtime, ONE B70 (card 0), 48 layers, 48.63 GB packed experts host-pinned,
21,552,729,600-byte admitted device expert cache (zero-copy misses, overlapped maintenance), resident lookups, HC p60fusion
+ hc-wide, wide64+halfcache, other-fusion, ordered-foreground retirement, tile16, bounded spin wait, kernel foreground token I/O,
BF16 KV, context 4096, **decode_mode plain (target only, no draft)**. **Record:** **35.926720 tok/s** class-balanced (packet182c
chain WS128, 2026-10-22 09:47-10:21 UTC, LocalMaxxing `cmvjejvoi03qcrf0138emu5a6`, 12/12 exact vs `iq3-p49-split32-v1`).
**Chain bar:** 36.645 (+2%). **Screen bar:** 36.106 (+0.5%).

Nothing here was built, run on a device, queued, committed or written into the repo. Every number is arithmetic on retained
receipts: packet182c's 12 x 99 record intervals (`evidence/card0-182-a/WS128/run/run/<prompt>/{timings.jsonl,result.json}`,
joined by global position with `run/run/cache.jsonl`), the chain's K1a/K1b zero-copy fixtures, the WS128 memory census /
DRM samples / admission plan, packet182's one-load bracket readout (`screen/evidence/card0-182-v5-a/.../summary.json`
`mechanism_readout`), and the two-card model of packet190's lever synthesis 4 for the per-layer comparison. Scripts beside this
file: `load_ws128.py` (loader + record-metric replay), `analyze_ws128.py` (anatomy, regressions, replays; output
`analyze-ws128-output.json`), `price_onecard_levers.py` (lever arithmetic; output `price-onecard-levers-output.json`),
`dnr-list.txt` / `all-dnr.txt` (all 308 DO-NOT-REPEAT.md files under `experiments/own-xpu-runtime`, 223 of them stage2 packets,
collected and grepped before anything was proposed). The loader reproduces 35.92672010504166 from the raw timestamps to 1e-12.

## 0. Answer

* **Premise corrections first.** (a) The one-card record line has **no MTP draft**: `decode_mode: plain`, every
  `draft_statistics` / `acceptance_statistics` / `hit_miss_cycle_statistics` field in the WS128 summary is null (count 0). There is
  no hit/miss cycle on one card; every token is one serial pass of 48 layers + head. One-card MTP was closed three times without a
  build (packet58h, packet58aa, packet170). (b) The brief's "0.58 ms/layer" is 27.75 ms / 48 including the head, the misses, the
  fill traffic and the host boundary; net of those the one-card layer body is **0.48 ms**, at parity with the two-card
  0.469-0.495 (the kernel dispatch tables of packet182c and the packet190 k3x selection are byte-identical, checked).
* **A.** Per token (99-interval window means, 1,188 tokens): interval **27.748 ms** = enqueue loop 4.890 (overlaps the device)
  + spin wait 21.030 + host-exclusive gap 1.793 (+ 0.035 timing row). The device is busy for at least enqueue + wait =
  **25.92 ms**; the host-exclusive gap is NOT device-idle time: 2.06 ms of it per two tokens is the LRU plan, which runs during
  the position and is absorbed by the wait (per-request differencing with the plan-free first request as control gives a hiding
  fraction of 0.94-1.13). The device-idle boundary gap is **~0.54 ms/token** (request 1 state-1 gap 0.658 minus its plan 0.121)
  plus the fill submission (0.32 ms on the 49.8% of tokens that submit fills). The serial terms, with their measured source:
  **48 layer bodies ~23.3 ms** (0.486/layer, the two-card all-resident rank-0 rate) + **head 1.40** + **expert-miss zero-copy reads
  1.0-1.5 ms** (regression 1.03 / K1 x fill bytes 1.44 / parity triangulation 1.19; the p58y-ratio 3.1 is excluded by the parity
  bound) + **fill-related 0.51** (contention on the wait 0.70 + host submission 0.32 per filled token, x 0.498) + **boundary gap
  0.54**; model sum 26.98, residual 0.77 (spin detection latency, publication 0.24, unmodelled). What binds: the 48 serial layer
  bodies (84% of the token); nothing overlaps them on a single CCS. Token I/O is 0.012 ms (done), publication 0.243 host,
  prepare 0.050, 1,118 kernel submissions and exactly 1 host wait per token, 269 voluntary context switches (spin tail).
  Expert cache: **15.82 fills / 31.37 MB per token** (fills are a lower bound on misses: the overlap pipeline plans from every
  other position; packet58y measured misses/fills = 2.17 at 18 GB, so the real miss count is between 15.8 and ~34 of 480,
  hit rate 92.9-96.7%; no route-ID census exists on this line - packet58ai's never completed). K1a/K1b: 33.79 MB fixture all-host
  1.933 ms vs VRAM 0.384 ms = 17.48 GB/s useful, **0.0458 ms per host-read MB**.
* **B.** Two-card B half: 11.90 ms for 21 layers + head = (11.856 - 1.404 head - 0.052 norm) / 21 = **0.495 ms/layer**; rank-0 A
  half 11.66 / 24 = 0.486; boundary body 0.469. One card: (25.92 device span - 1.40 head - 1.2 miss - 0.35 contention) / 48 =
  **0.479 ms/layer**. The per-layer kernel cost is the same; the one-card token is 2.05x the two-card hit cycle (27.75 vs 13.51)
  because (i) the two cards run two halves concurrently through speculation (hit cycle = half the total work of both cards), (ii)
  the one card adds 1.0-1.5 ms of host reads for the 3-7% of expert selections that miss the 21.55 GB cache, (iii) 0.5 ms of fill
  traffic contention/submission, (iv) 0.5 ms of boundary gap vs the two-card 0.04 ms of gaps (its boundary and envelope are
  overlapped by the other rank). The "larger per-card working set" costs nothing per layer: the dense/HC/attention weights are
  resident on both lines; only the expert bank residency differs (two cards hold all 48.6 GB of experts, one card 21.55 GB).
* **C.** Priced (replay on the record intervals; the flat-saving curve is 0.1 ms -> +0.36%, 0.2 -> +0.72%, 0.5 -> +1.83%,
  **0.545 ms/token = chain bar**, 0.138 = screen bar): (1) **cache +1.5 GB (23.05 GB): +0.58-0.84%** (wide +0.51-0.99%); +2.0 GB:
  +0.77-1.12%; the chain bar needs a 32% miss-byte cut = +3.5-5.1 GB of cache (does not exist on a 32 GB card); all experts resident
  (impossible, 48.6 GB) would be +5.9-7.5%; memory headroom: 2.12 GB of unallocated allowance inside the 29.963 GB bound (census
  live 27.84; workspace live 0.30 of the 2.15 GB workspace+transaction bounds), physical room under the 32.0e9 floor and 1.5 GB
  reserve 2.06 GB (DRM peak 28.44 GB, constant over 13 samples; measured driver overhead 0.60 GB > the 0.54 GB allowance).
  (2) prefetching next-layer experts: routes are unknown until that layer's router (packet125 DNR), router-predicted prefetch lost on
  every scenario (packet138), post-router demand copies measured -52.6% (packet58am); 100% of miss bytes are exposed inside the
  expert kernels on the single CCS; fills are already overlapped (packet58v) but contend: **0 open**. (3) draft-keyed placement:
  no draft on this line: 0. (4) one-card draft: favorable cycle 48.1 ms (27.75 + 2 x 9.21 measured M=2 row cost + 1.53 draft +
  0.45 miss increase) = 37.0 tok/s (+3.0%) only if feedback/state/head/pollution are free; packet170's charged sensitivity is a
  63.6 ms cycle = 28.0 tok/s (-22%); closed (58h/58aa/170), revisit needs measured current-line class shares. (5) ports: dispatch
  identical, hc-wide/wide64+halfcache/p109/p76/kernel-I/O ported, p105 head split / p153 static snapshot / k3x boundary / p137
  token input are two-rank mechanisms: 0. (6) host issue path: base device-idle gap 0.54 ms; realistic trims 0.10-0.35 ms =
  **+0.36-1.27%**, each item (publication 0.20, non-blocking token input 0.05-0.30 assumed, spin tail 0.05-0.08, timing row 0.035)
  alone inside drift; ceiling if the gap were zero +1.97%. (7) the scopes point at fill contention: filled tokens cost 1.21 ms
  more than unfilled (packet182 B0: 1.115), **0.51 ms/token = +1.86% ceiling**, but the bytes set the cost (packet174/182) and
  only capacity moves fewer bytes; and at the metric's structure: the record is the mean of the prose median (customer-email
  36.59, decision-memo 34.52) and documentation (technical-guide 36.30), prompts with 28-40 MB/token of fills.
* **D. Nothing open reaches +2%. Reaches +0.5%: only cache capacity (+1.5 GB: +0.58-0.84%; +2.0 GB: +0.77-1.12%) and, on paper,
  a three-item host-gap composite (+0.36-1.27%, every part assumed).** A per-layer kernel saving would need 11.4 us on all 48
  layers (2.3% of a layer) for the chain bar; the two-card synthesis found no open class item above +1.16% at 100% transfer, and
  this line runs the same kernels. Recommendation: **ONE capacity screen, `packet58-onecard-cache23`** (section 5): the 182c
  selection unchanged plus a `cache_cap max|max23` view dimension at 23,049,601,024 bytes (+1.4968 GB, 256-aligned), one load
  A/B/A/B/A, ~14 min on card 0; priced **+0.58-0.84% (wide +0.5-1.0%)**, screen bar expected, chain bar not; it requires a native
  rebuild (the engine hard-codes `max` = 21,552,729,600 and refuses other arenas) and a re-partition of the device bound that
  packet58x's DNR allows only with "a new measured lifetime proof and a separately admitted policy" - the 182c receipts supply the
  proof (13 DRM samples at 28.44 GB, workspace live 0.30 GB of 2.15 GB bounds). If the owner wants only +2% candidates: there are
  none on one card; the honest next step is then a measurement, and the one with information value is packet58ai's route-ID
  census (prepared, d-smoke pending), which pins the 2x-uncertain miss count and the capacity price.

## 1. Identity and what the receipts contain

| | |
|---|---|
| Record run | `packet182c-chain/evidence/card0-182-a/WS128/` (chain `packet58-onecard-182-a`, 09:47-10:21 UTC, 7 windows passed) |
| Native argv | `--card 0 --cards 1 --context 4096 --max-new 128 --stage decode --memory resident --miss-path zero-copy --timing token --lookups resident --hc p60fusion --hc-geometry hc-wide --experts wide64+halfcache --other-fusion fused --retirement ordered-foreground --cache-maintenance overlap --cache-cap max --cache-bytes 21552729600 --wait-policy spin --foreground-io kernel` |
| Engine | `build/device/own-rt-iq3` sha256 `1b41fb4d...` (byte copy of packet176's), dispatch `dispatch-speed6.json` (identical to packet190's k3x selection table) |
| Metric | per prompt 99 / (t100 - t1); median per class; median of the 6 class medians = (prose 35.555 + documentation 36.298) / 2 |
| Per-token fields | `wall_ms, enqueue_loop_ms, wait_ms, prepare_ms, transfer_wall_ms (head/tail/route_log), kernel_submissions (1118), host_waits (1), context switches, faults`; **device scopes are zero placeholders** (`timing=token`, profiling off) |
| Cache stream | `cache.jsonl`: one row per global position (2,386 = sum of prompt + 127), cumulative fills / fill bytes / publication counters, `plan_ms`, `state` (1 = planned, 2 = fills submitted) |
| Memory | census: device 27,841,904,372 (cache 21.55 GB, non-expert weights 5.82 GB incl. 0.84 GB head, workspace 0.30 GB live, KV 0.12, recurrent 0.06); host-pinned 48,633,091,712; DRM VRAM 27,774,044 KiB after load and at all 12 request resets |
| Host | RssAnon 28.76 GB (resident lookups 29.32 GB planned), 0.005 major faults/token, owner thread 81% of one core |
| Cold start | load + pin 209.8 s; first prompt prefill 27.65 s (empty content-independent cache; the first request's fills are charged to it) |

Premise check against the brief: the draft, acceptance, hit/miss and "draft + target serially" items do not exist on this line.
The one-card line is target-only by design (packet58ag DNR: "No two-card head or speculative draft path on this target-only
line"); packet58h (24.62 projected vs 28.8 required), packet58aa (25.0-29.2 projected vs 30.7 required) and packet170
(conservative cycle 63.6 ms vs 51.2 required) all closed it without a build.

## 2. The one-card per-token model (question A)

### 2.1 Anatomy (window means, ms; `analyze-ws128-output.json`)

| | all (1188) | fills submitted (592, state 2) | no fills (596, state 1) |
|---|---:|---:|---:|
| interval | **27.748** | 28.357 | 27.144 |
| enqueue loop (1,118 submissions; overlaps the device) | 4.890 | 4.922 | 4.858 |
| spin wait (one host wait per token) | 21.030 | 22.416 | 19.654 |
| prepare / transfer (head + tail) / publication host | 0.050 / 0.012 / 0.243 | | |
| host-exclusive gap = wall - enqueue - wait | 1.793 | 0.981 | 2.599 |
| plan_ms (one plan per 2-position transaction) | 2.064 | | |
| fills / fill MB | 15.82 / 31.37 | 31.76 / 62.95 | 0 |
| voluntary context switches | 269 | 288 | 252 |

Where the plan sits: `cache_plan_during_position()` runs after the position's kernels are enqueued (packet58v design); the
state-1 gap regresses on `plan_ms` with slope **1.002** (intercept 0.53) while the state-1 wait falls with it, and per request
the state-2 minus state-1 wait difference equals the plan plus the fill contention measured on the plan-free first request
(1.05 ms): hiding fraction 0.94 (code-review), 1.13 (sql-debugging), 0.99 (decision-memo). **The plan is hidden under the device
work; the host-exclusive gap is not device-idle time.** The device-idle boundary is the plan-free gap: request 1's state-1 gap
0.658 - plan 0.121 = **0.54 ms/token**, plus 0.32 ms of fill submission on state-2 tokens.

### 2.2 Serial terms and the binding term

```
T = 48 layer bodies (23.3 @ 0.486/layer, two-card all-resident rate; 22.5-23.8 at 0.469-0.495)
  + head 1.40
  + expert-miss host reads 1.0-1.5          (regression 1.03 | K1 0.0458 ms/MB x 31.4 MB = 1.44 | parity 1.19 [0.76-2.00])
  + fill-related 0.51                        (contention on the wait 0.70 + submission 0.32, per filled token, x 0.498)
  + device-idle boundary 0.54                (publication 0.24 inside it)
  = 26.98; measured 27.75; residual 0.77 (spin detection latency, unmodelled host work)
```

Why the p58y-ratio miss estimate (3.1 ms) is excluded: the one-card device span lower bound (25.92) minus the head minus 48 layers at
the two-card rate leaves 0.76-2.00 ms for everything miss- and fill-related; 3.1 does not fit. The regression on miss intensity
(unfilled tokens' wall vs the next fill boundary's MB: **0.033 ms/MB**, the same slope packet182 found on packet171b) prices the
marginal miss cost at 1.03 ms/token; the K1 fixture's 0.0458 ms/MB x the fill bytes gives 1.44. Central value used: **1.2 ms**.

The binding term is the serial chain of 48 layer bodies on one CCS (84%); misses (4%), fills (2%) and the boundary (2%) are the
only terms that differ from the two-card per-layer rate. Nothing overlaps a layer body on this card (B70 has one CCS; packet58al:
no compute on BCS).

### 2.3 Distribution and what sets the metric

Intervals: p5 25.08, median 26.67, mean 27.75, p95 33.90, max 52.4 ms. Per request (tok/s, fill MB/token): incident-retrospective
32.48 (55.6, the cold first request), code-review 37.05 (25.1), customer-email 36.59 (29.3), sql-debugging 34.05 (42.5),
release-plan 34.51 (41.3), benchmark-analysis 37.56 (23.6), architecture-tradeoff 37.68 (22.2), bug-report-synthesis 38.18
(18.3), technical-guide 36.30 (28.5), risk-register 37.09 (25.7), performance-hypotheses 37.46 (24.0), decision-memo 34.52
(40.3). Rate vs fill MB across prompts: -0.15 tok/s per MB; the metric's two middle classes (prose, documentation) carry 28-40 MB
of fills per token. The cold first request does not reach the metric (operations median = release-plan).

### 2.4 Replay thresholds (record intervals)

| flat saving per token | tok/s | gain |
|---:|---:|---:|
| 0.100 | 36.056 | +0.36% |
| **0.138** | **36.106** | **+0.50% screen bar** |
| 0.200 | 36.187 | +0.72% |
| 0.300 | 36.318 | +1.09% |
| 0.500 | 36.584 | +1.83% |
| **0.545** | **36.645** | **+2.00% chain bar** |
| 1.000 | 37.266 | +3.73% |
| 2.000 | 38.710 | +7.75% |
| 48 x 0.0114 ms per layer | 36.645 | +2.00% (11.4 us per layer = 2.3% of a 0.486 ms layer) |
| 48 x 0.0029 ms per layer | 36.106 | +0.50% |

## 3. One card vs the two-card B half (question B)

| | two cards (packet190 k3x, per hit 13.51 ms) | one card (packet182c, per token 27.75 ms) |
|---|---|---|
| rank-0 A half (24 layers, all experts resident) | 11.927 = 11.660 completion + 0.267 envelope -> **0.486/layer** | |
| rank-1 B half (21 layers + head) | 11.902 = 10.401 layers (**0.495/layer**) + 1.404 head + 0.052 norm + 0.046 envelope | |
| boundary body (3 GDN layers) | 1.406 -> **0.469/layer** | |
| 48 layers on one card, net of head/miss/contention | | (25.92 - 1.40 - 1.2 - 0.35) / 48 = **0.479/layer** |
| expert misses from host | 0 (two cards hold 48.6 GB) | 1.0-1.5 ms (3-7% of selections; 31-68 MB/token over PCIe at 17.5 GB/s useful) |
| fill traffic | none | 0.51 ms/token (63 MB per filled token on BCS, contends with zero-copy reads) |
| gaps / boundary | G 0.038 (hits); boundary and envelope overlapped by the other rank | 0.54 ms device-idle at every position + 0.32 on fill tokens |
| draft | 1.53 ms, binds the ready side by 0.048 | none |
| why 2.05x | hit cycle = (rank-0 work 13.41 + rank-1 work 13.43) / 2: both cards busy 99.3% | one serial chain of 48 bodies + head + 2.5 ms of cache/boundary terms |

So the per-layer kernel cost is at parity (dispatch identical; 58ag ported hc-wide, wide64+halfcache, p109 other-fusion, p76
retirement; p176 kernel I/O ported on both). The extra 1.3 ms/token vs 48 x 0.486 + head is the whole cache/boundary story; the
rest of the 2x is topology (two cards in parallel), which no one-card lever touches.

## 4. Lever prices (question C)

| # | Lever | Arithmetic (ms/token saved -> replay) | Price | Status / rows |
|---|---|---|---:|---|
| 1 | **Device expert cache +1.5 GB (23.05 GB)** | capacity +6.96%; miss/fill bytes -9.3% to -13.6% (native elasticity -1.34 per % from packet58y 18 GB 42.6 MB vs 182c 31.4 MB; replay -1.95 per % from packet58x ADMISSION 21->21.55 GB); x (miss 1.2 + fill 0.51) = 0.16-0.23 ms | **+0.58-0.84%** (wide, miss 1.0-1.5: +0.51-0.99%) | open; needs a rebuild (engine literal `max`=21,552,729,600; `cache_capacity()` refuses other arenas) + a device-bound re-partition (packet58x DNR: "new measured lifetime proof and separately admitted policy"); fits: DRM 28.44 + 1.5 + 1.5 reserve = 31.44 < 32.0 floor; host +1.5 GB backing (120.6 GB available vs 100.5 required) |
| 1b | cache +2.0 GB (23.55 GB) | -12.4 to -18.1% bytes -> 0.21-0.31 ms | +0.77-1.12% | as above; leaves 0.56 GB of the 2.06 GB physical room, driver overhead already 0.06 GB over its allowance |
| 1c | chain bar via capacity | needs a 32% byte cut = +3.5-5.1 GB | impossible on 32 GB | - |
| 1d | all experts resident | 1.54-1.95 ms (3.6 at the excluded p58y ratio) | +5.9-7.5% ceiling | impossible (48.6 GB); says the line is bounded by the 48 serial bodies, not by the cache |
| 2 | Prefetch next layer's experts on the copy engine | routes unknown until the router; 100% of miss bytes exposed inside the kernels; fills already overlapped | 0 | closed: packet125 DNR ("do not prefetch next-layer experts before that layer's router"), packet138 (router-predicted prefetch loses every scenario), packet58am (post-router demand copies **-52.6%**), packet125 micro (best transport 1.27x < 1.5x gate; tile16 adopted) |
| 3 | Placement keyed by draft routes | no draft on this line | 0 | n/a; packet58i frequency prefetch -28%, LFU -53% (replay) |
| 4 | Draft on one card (M=2) | favorable: 27.75 + 2 x 9.21 (packet151e measured partial M=2 half) + 1.53 + 0.45 = 48.1 ms / 1.787 = 26.9 ms/token = 37.0 tok/s (+3.0%) with feedback/state/head/pollution at zero; packet170 charged cycle 63.6 ms = 28.0 tok/s | -22% to +3% | closed: packet58h, 58aa ("do not add a resident draft beside an unchanged 21.553 GB cache"), 170 ("do not set unknown feedback ... to zero") |
| 5 | Unported two-card kernel wins | dispatch tables identical; per-layer 0.479 vs 0.469-0.495 | 0 | p105 head split, p153 static snapshot, V3/k3x boundary, p137 token input, p150 scopes are two-rank mechanisms; 58ag ported the rest |
| 6 | Host issue path | device-idle gap 0.54: publication construct/upload/scatter 0.20 (58aq), drain 0.018 under spin, non-blocking token input 0.05-0.30 (assumed, p171 row 2), spin tail 0.05-0.08 (assumed, row 3), timing row 0.035 | **+0.36-1.27%** realistic (0.10-0.35 ms); +1.97% if the gap were zero | open but every item alone is inside drift (0.02-0.1%); p171 row 1 closed (171b +0.40%), row 4 dead under spin, row 5 (reply-first) does not change intervals |
| 7 | Fill contention + submission | 1.21 ms per filled token (182 B0 1.115) x 0.498 = 0.51 | +1.86% ceiling | closed as a timing lever (packet174 kick -0.02%, packet182 pacing 0-0.3%: bytes set the cost); only #1 moves fewer bytes. Note: packet182's revisit condition (>= 1.1 ms per filled token) is numerically met, but no byte-reducing mechanism exists except capacity |
| 8 | Admission policy (two-hit) | packet58i replay: -8.4% fills, +2.95% misses -> 0.084 x 0.51 - 0.03 x 1.2 = +0.01 ms | ~0 | not worth a packet |
| 9 | Per-layer kernel class saving | chain bar 11.4 us/layer on all 48 (2.3%); screen 2.9 us | best open item packet104b <= +1.16% at 100% micro transfer (+0.2% at 20%) | same kernels as two cards; packet190 synthesis 4: no open class mechanism at +2% |
| 10 | Publication off the boundary (packet58ar design) | 0.200 ms/position measured under spin (packet171), drain <= 0.018 | <= +0.72% | packet171: "dead under spin"; do not package 58ar |

Measurement noise on this line: packet182 v5 warm-control drift 0.018% (A1/A2 34.590/34.584), chain vs bracket B +0.07%
(35.927 vs 35.951/35.955); the first-view warm-up effect is 0 since packet58aj (A0 34.579). A +0.5% screen is therefore
resolvable on this line (unlike the two-card 0.28% drift).

## 5. Ranking and the one next packet (question D)

| rank | lever | price | +2%? | +0.5%? |
|---|---|---:|---|---|
| 1 | cache +1.5 GB / +2.0 GB | +0.58-0.84% / +0.77-1.12% | no | yes (expected) |
| 2 | host boundary composite (publication construction off-boundary + non-blocking token input + spin tail) | +0.36-1.27% | no | maybe; three mechanisms, each assumed and inside drift |
| 3 | packet104b gate/up tile16 + half-cache | <= +1.16% at 100% transfer, +0.2% expected | no | unlikely |
| 4 | fill bytes via admission policy | ~0 | no | no |
| - | prefetch / demand transfer / draft / ports / publication | 0 or closed | | |

**Recommendation: `packet58-onecard-cache23` (one-load capacity screen, lane A, card 0, ~14 min).**

* **Selection keys:** the packet182c record selection unchanged (`hc=p60fusion, hc_geometry=hc-wide, experts=wide64+halfcache,
  other_fusion=fused, retirement=ordered-foreground, lookups=resident, cache_maintenance=overlap, miss_path=zero-copy,
  wait_policy=spin, foreground_io=kernel, memory=resident, context 4096, BF16 KV, down-tile16, dispatch-speed6`) plus a new
  `cache_cap` view value `max23` = **23,049,601,024 bytes** (21,552,729,600 + 1,496,871,424; 256-byte aligned; +6.95%), switched at
  the drained view boundary exactly as `18GB|max` is today (`cache_capacity()`: drain, quiesce, `reset_capacity`, republish, view
  starts empty). The arena is allocated once at the new maximum in every view; A views use 21,552,729,600 of it (the packet58x
  design: "both views retain the maximum allocation").
* **What must change (a rebuild, not a flag):** `main.cpp` `cache_capacity()` hard-codes `max` -> 21,552,729,600 and requires
  `arena.bytes == 21552729600`; `memory_plan.py` / `onecard_admission.py` carry the 29,963,128,848 bound (= 32.0e9 floor - 1.5e9
  reserve - 536,870,912 driver, margin 240 B). The new plan re-partitions, not raises, the device budget: driver allowance
  536,870,912 -> 671,088,640 (measured overhead 598.7 MB), so the device-owned bound becomes 32.0e9 - 1.5e9 - 671,088,640 =
  **29,828,911,360**; expert_cache_arena +1,496,871,424; the three transient bounds (control transaction 1,073,741,824 + workspace
  1,073,479,680 + transfer 268,435,456 = 2,415,656,960) -> 784,567,808 (2.65x the 295,612,132 B of transient device allocations
  live in the 182c census; e.g. 268,435,456 / 402,653,184 / 113,479,168). New category sum 29,828,911,120, margin 240 B as today.
  Lifetime evidence: DRM total constant at 27,774,044 KiB across load and all 12 request resets; host-side post-load shadow peak
  659 MB. Expected DRM after load ~29.94 GB (< the 30.5 GB native/supervisor guard). Host admission +1,496,871,424 backing ->
  100,487,123,456 (MemAvailable with the owner's
  endpoints stopped was 120.6 GB on 2026-10-22). This is the packet58x DNR's "new measured lifetime proof and separately admitted
  policy"; the proof is the 182c receipts (`census.json`, 13 `drm-memory-*` samples, `window.json postload_memory`), the policy is
  the coordinator's to admit (owner rule 2026-10-16: decide, do not ask). Sealed-lane literal archaeology: grep the native and
  Python trees for `21552729600`, `29963128848`, `18000000000`, `"max"` before the build (packet58x's own DNR row: "recheck every
  allocation gate when capacity changes").
* **Rows (one proposal, < 20 min):** K1a, K1b (unchanged fixtures, ~1 min), then ONE load `max / max23 / max / max23 / max`
  (A0/B0/A1/B1/A2), 12 x 128-token requests per view, no separate smoke (A0 is the exact warm-up as in packet58as/176/182);
  packet182's identical shape took 793 s; plan 700-1200 s, watchdog 7200 s. Native after-load admission and the live supervisor
  reject DRM occupancy above 30.5 GB (58x guard, unchanged). PAUSE-B held; endpoints stopped as for packet182.
* **Decision rule:** both B views >= 1.005 x every warm A, warm drift <= 3%, 60/60 exact vs `iq3-p49-split32-v1`; mechanism
  readout kept on every outcome: fills/token and fill MB/token per view (expect B <= 0.91 x A), filled-token wait excess, state-1/
  state-2 gaps, DRM peak per view. Chain (seven windows, `--cache-bytes 23049601024`) only if min gain >= +2% - **not expected**;
  a +0.5-1.0% win is banked as a composable screen result and becomes the new control for the next one-card screen.
* **Kill rules:** (1) any view not 12/12 exact -> stop, no chain; (2) native after-load DRM > 30.5 GB or census > the new bound ->
  the window refuses before WSCREEN (existing guard), do not lower the reserve or the driver allowance to make it fit; (3) B fills/
  token not reduced by >= 8% vs A (readout) -> the elasticity assumption is wrong at this size: close capacity at 23 GB regardless
  of speed; (4) warm drift > 3% or either warm A view below 35.2 tok/s (the A arm is the 35.93 record line; packet182's B views
  measured 35.951/35.955 in the same shape) -> host disturbed, report and do not rerun automatically; (5) the admission
  re-partition cannot be derived from the
  182c receipts alone (e.g. a transient peak above the new workspace bound in any sample) -> do not build; (6) build/seal must not
  touch packet182c (post-chain tool fixes break descendant seals).
* **Priced gain with uncertainty:** +0.58-0.84% central (elasticity -1.34 to -1.95 per % capacity; miss cost 1.2), +0.51-0.99%
  wide (miss cost 1.0-1.5). Precedent: packet58x measured +4.13% at +19.7% capacity against its +2.26% replay projection (ratio
  1.83), but that projection priced fill bytes at a 25 GB/s copy proxy and credited no zero-copy miss term, which this price already
  includes; applying the ratio naively would say +1.1-1.5%. Honest range +0.5-1.0% with upside to ~1.5%. Probability of clearing
  the screen bar: high; of the chain bar: ~0.

**If the owner wants only +2% candidates:** none is open on one card. The next step is then a measurement, and the one with the
most information value is **packet58ai's route-ID miss census** (prepared; its c-smoke failed on packaging, the d-smoke proposal
`packet58ai-census-d-smoke-A` exists): it counts misses against the published pointers (the 2x uncertainty 15.8-34 misses/token
that spans the capacity price), gives per-layer hit rates (layer 2's IQ3_XXS experts are 18% larger and miss more: 88.9% vs 93.2%
on 58g) and the resident-vs-miss kernel partition. Priced gain 0 tok/s; it would turn lever #1's +0.58-0.84% into a point estimate
and either justify the full 2.0 GB or close capacity. It does not create a +2% lever: even all-resident is +5.9-7.5% and that
needs 48.6 GB.

**Why the one-card line is at a structural floor (and the Strata gap is not closable on this line):** 27.75 ms = 48 serial layer
bodies at the measured B70 rate (23.3) + head (1.4) + 2.5-3 ms of cache and boundary terms. Removing every cache and boundary term
(impossible) gives ~24.7 ms = 40.5 tok/s. Strata's 52-62 tok/s on a 5070 (16-19 ms/token) is below one B70's serial 48-layer body
time; on this hardware the only way past 40 tok/s with one card is two tokens per pass (MTP at M=2, closed at the measured 9.21
ms/half row cost) or a different per-layer kernel floor (every class closed at its measured ceiling, packet190 synthesis 4). The
two-card line reaches 62.35 only by running two halves concurrently.

## 6. DO-NOT-REPEAT rows checked (`all-dnr.txt`, 308 files, grepped for LRU/victim/plan/capacity/cache bytes/reserve/headroom/
prefetch/two-hit/admission/MTP/draft/cache_cap/workspace)

Capacity: packet58x ("spend physical headroom by removing workspace or reserve: excluded; revisit: new measured lifetime proof and
separately admitted policy"; "recheck every allocation gate when capacity changes"); packet58i ("spend 5.89 GB physical VRAM
headroom: not admitted; revisit: exact freed-byte and peak-lifetime proof"); packet58h ("do not reclaim headroom by changing
memory exclusions, swap, page cache, cache capacity, KV precision or the reserves" - this packet keeps all of those: the floor,
the 1.5 GB reserve, BF16 KV and the host reserve are unchanged; it re-partitions the transient allowances against measured
lifetime samples); packet58al ("packet58x cache capacity: 21.55 GB gain already adopted; same cache capacity, no temporary stage
compute reuse, no reserve borrowing" - a boundary of the demand-transfer packet, not a closure of capacity); packet58u (new cache
scope "requires a new reviewed and sealed bound" - which is what the packet does). No row closes a larger admitted cache with a
lifetime proof; the only measured capacity row (58x) won +4.13%.
Prefetch / transfer: packet125, packet138, packet58al/58am, packet119, packet95/100 (E3), packet58i (frequency prefetch, LFU).
Draft: packet58h, 58aa, 170, 58ag, 58y ("No MTP ... speculative cache predictor is reopened here").
Host path: packet171/171b (row 1 closed), packet56x (no millisecond polling), packet58aq/58ar (publication drain dead under spin),
packet174/176/182 (fill kick, memcpy on the compute queue, pacing/deferral, the "~1.0 ms/token" artifact, `moved_rule`).
Kernels: packet104/104b, 110, 141 (two-card cold/warm ratios are streaming cost), 142/145 (layouts null), 183 (S1/S2 dense).
Process: packet182 (commit summary/window right after a window; use `chain/derive_chain.py` + `script_argv_check.py`; never the
quiet2 scripts that delete PAUSE files; `--postnative-check` now has a completed one-card chain tree to run against).

## 7. Scripts and outputs beside this file

* `load_ws128.py` - loads the 12 requests' `timings.jsonl` / `result.json` / `cache-stats.json`, joins `cache.jsonl` by global
  position (prefill positions = prompt tokens - 1, then 128 generated), reproduces the record metric (35.92672010504166) two ways,
  writes `ws128-rows.json` (1,536 rows; 1,188 in the metric window).
* `analyze_ws128.py` - anatomy by state, regressions (same-token fills, next-fill control, t+2 fills, plan), hit/miss proxies, K1
  penalty, replays (flat savings, fill excess removed, gap removed, miss-cost scenarios, per-layer savings), thresholds;
  `analyze-ws128-output.json`.
* `price_onecard_levers.py` - the accounting, memory headroom and every lever price above; `price-onecard-levers-output.json`.
* `dnr-list.txt`, `all-dnr.txt` - the DO-NOT-REPEAT corpus collected before proposing.
