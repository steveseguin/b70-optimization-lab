# Packet173: two-card lever table, ready for the packet168 census

This is CPU-only preparation on bundle 8 (packet136, **58.798108759 tok/s**,
`iq3-p49-split32-v1`, 24/24 layers, rank-1 MTP, draft prefix 80,128). Nothing
here is a measurement or a speed claim. The class sizes below are **priors**
until `packet168` reports.

## Ten-minute procedure after the census

```bash
cd experiments/own-xpu-runtime/stage2/packet173-twocard-lever-table
nice -n 19 taskset -c 8-15,24-31 python3 -B rank_levers.py \
  --census ../packet168-twocard-body-census/evidence/device-census-<id> </dev/null
```

The script reads `census-report.json`, which holds the rank0+rank1 summed
marginals. It also reads `run/census-input.json` for the real **per-rank**
split. It then replays packet160's 1,188 record intervals exactly: rank 0's A
and C fall by f·m_rank0 and rank 1's B by f·m_rank1. The output ranks every
lever at its low, mid and high net fraction f. Build the top row whose mid
value is at least +2%. If no row reaches +2%, build the top row anyway only if
its mid value is at least +1% and lane B is otherwise idle. Otherwise build
nothing: run the attribution follow-up named below for the class that came out
largest. `prior-ranking.txt` holds the same table for three prior scenarios.

## (a) Thresholds from the real interval (packet160 replay, `thresholds.json`)

The replay reproduces 58.798108759 tok/s exactly. Its interval statistics:

| Interval statistic | Value |
|---|---|
| Hit interval | 14.704 ms |
| Miss interval | 25.613 ms |
| Pooled | 17.055 ms |
| Number of hits / misses | 932 / 256 |

B (rank 1 body plus head) wins every race. B − A is 0.606 ms on average and
0.544 ms at the 10th percentile.

| Gain | Symmetric (both ranks), ms/half | Same, as a **summed census** reduction | Rank-1-only ms/half | Rank-0-only ms/half |
|---|---:|---:|---:|---:|
| +0.5% (kill gate) | 0.070 | 0.140 | 0.085 | 0.399 |
| +1% | 0.139 | 0.278 | 0.168 | 0.795 |
| **+2% (worth building)** | **0.275** | **0.550** | 0.333 | 1.574 |
| +3% | 0.409 | 0.817 | 0.496 | 2.338 |
| +3.5% (owner's "0.6 ms/token at 17.0") | 0.475 | 0.949 | 0.584 | 2.714 |

**The units trap.** The census sums both ranks, but the two halves overlap.
So 1 ms of summed census reduction is worth only about 0.6 ms/token on the
critical path. "0.6 ms/token" therefore means a 0.95 ms **summed** census
reduction, not 0.6 ms.

Two further limits apply:

* A rank-1-only change saturates at about +3.85%, once A becomes critical.
* A rank-0-only change acts only through the misses.

Every lever below changes kernels that both ranks run, so the symmetric column
applies.

**Per-class build threshold:** the measured summed marginal must satisfy
m_c ≥ 0.550 / f_mid(lever). For D2 (f_mid 0.04), dense_hc must be at least
13.8 ms for a +2% mid value, and at least 7.0 ms for +1%. For D1 (0.016) the
same thresholds are 34 ms and 17 ms.

## (b–e) Ranked levers

The ranking uses the prior scenarios in `prior-ranking.txt`:

* **Proxy:** 2 × the packet140 rank-1 proxy, mapped to `classify()`.
* **Cold-weighted:** the packet141 cold/warm ratios.
* **Expert-heavy.**

The order is the same under all three. The top lever's mid value is
+1.45% to +1.80%. **No lever reaches +2% on priors.** The census decides
whether D2 is worth building.

| Rank | Lever | Class | Mechanism (not closed) | Closures checked | Mid gain (proxy) | Time |
|---|---|---|---|---|---:|---:|
| 1 | **D2 dense-weight L2 warm-ahead** | dense_hc (+ router/shared-expert tuple weights) | The latency-bound kernel before each route-independent dense GEMV issues L2-only prefetches of that GEMV's weight bytes. It writes nothing and changes no arithmetic. Packet141 measured cold − warm ≈ 0.78 ms/half of dense excess on rank 1. | p119 warmed DOWN *during* bandwidth-bound gate/up (1.079×, closed); this lever runs in latency-bound predecessors. p138/p125 prefetched route-*predicted* experts; dense weights are route-independent. p142/p145 order600 layout was null. p144 warmed during correction. p34 graph replay. | +1.57% (0.78–2.78) | 4 h |
| 2 | D1 same-bit scale multicast | dense_hc | p140 N1 inside `p33::dense_lane`. A subgroup broadcast of the shared Q6/Q8 scale word replaces the duplicate loads; the chains and split32 tree are unchanged. | p140 closed it only at its +3% admission and never built it. p81 (load-count cut was neutral) is negative evidence. p74/p93 packed formats. p72 occupancy. p104 tile16. | +0.62% | 3 h |
| 3 | R1 router-GEMV last-group route election | router_shared_expert | p164 DESIGN: the last workgroup of the router GEMV runs the unchanged route-fast top-k. | p164 closed only the CPU *latency* selection (visible gaps 0.003 ms/half). p73/p78/p109 already fused. p112 pruned top10 lost. | +0.36% | 6 h |
| 4 | N3 producer RMS leaf partials | norms_glue | p140 N3. | p94 duplicated consumers; p46 four-WG upper tree; p78. Even deleting the whole class is below +3%. | +0.28% | 5 h |
| 5 | G1 gated norm folded into the recurrence epilogue | gdn | **Novelty check first:** `p82b_recurrence.hpp:111` already has `Kernel<SplitNorm>`. Drop G1 if the bundle-8 plan has no separate `gdn_norm_gate` launches. | p67/p82/p82b prepass and barriers; p113 row schedule; p107 nonfinite. | +0.24% | 4 h |
| 6 | E1n2 40-bit IQ2 cell, same 840-byte row | routed_experts | p140 N2. | Closed and not repeated: p95 E2/E3, p99 SLM/bytepair, p102, p104/104b tile16, p115 GRF, p119 warm, p162 enum11 (4.8× slower), p81 packed loads. | +0.22% | 7 h |
| — | none | attention (QSA kernels only; projections are dense_hc) | — | p116, p107, p44/p49, p72 wide64, p142 order600 | 0 | — |
| — | none; attribution only | residual (transfer, split head, mailbox, overlap) | Subtraction only, and probably negative because the halves overlap. Act only if it exceeds +1 ms; then trace with a p154-style scope. | p127 head re-split −1.95%; p160 head donation ≤ +2.235%; p161; p93x; p149/p160 80 µs exchange; p141; p156/p158 draft closure; p153 +0.35% | 0 | — |

**Census outcomes that change the order:**

* If dense_hc is at least 13.8 ms, D2 becomes "worth building".
* If routed_experts or router_shared_expert comes out more than 2× its prior,
  the classes contain a non-kernel cost such as cache interference. Do not
  build E1n2 or R1. Run a cold/warm split of that class instead (the p141
  method).
* If the residual is above +1 ms, run the attribution first.

### (c) Kill test (identical for every lever)

1. **Smoke:** a 12 × 64 composed smoke with the flag on.
2. **Bracket:** one load on lane B (cards 2+3), running v5 `C0/X1/C2/X3/C4`:
   * C0 is the excluded warm-up.
   * The controls run with `--<flag> off`, the parent default. The candidates
     run with the flag on.
   * The flag switches at view boundaries through a native switch/reset (the
     packet142 `v5/bracket.py:53` `switch_reset` pattern). Each switch calls
     the same setter that the CLI flag calls.
3. **Pass** only if all of the following hold:
   * both X views beat **every** warm control by at least +0.5%;
   * the drift across warm controls is at most 1%;
   * all 60 requests are exact against `iq3-p49-split32-v1`;
   * per-prompt draft acceptance is unchanged.

   Never relax this gate after a failure.
4. **D2 and D1 only:** before the bracket, run a 10-minute device micro of the
   paired predecessor and GEMV (both orders, two processes). Proceed at
   ≤ 0.97× for D2; p119 failed at 1.079×. Proceed at ≤ 0.95× for D1.

### (d) Source sites in the bundle-8 tree (`base/` = packet136 at HEAD)

| Lever | Sites (file:line in `base/`) |
|---|---|
| D2 | Predecessors: `p94_norm.hpp:53` (HC norm nd_range), `p78_norm.hpp:27`, `p82b_recurrence.hpp:111,125` (recurrence), `p109_route.hpp:40,57` (route). Add a prefetch-tail argument (pointer, bytes) that the plan binds to the *next* GEMV's weights. Bind it at the nongemv spec build in `main.cpp:1277-1351`, using the launch order from `main.cpp:490-530`. Successor GEMVs: `main.cpp:1269` (`dense`), `p39_fused.hpp:86-87`. |
| D1 | `p33_candidates.hpp:76-81` (`p33::dense_lane`) and its fused callers at `p39_fused.hpp:86`. |
| R1 | `p109_route.hpp:40-57` and `p109_fusion.hpp` (router tuple), following `packet164-route-fusion/DESIGN.md`. |
| N3 | The combine epilogue `s.fused_combine_norm` at `main.cpp:1351`; `p94_norm.hpp`. |
| G1 | `p82b_recurrence.hpp:111` (`SplitNorm`); `main.cpp:366,1291,1604` (`gdn_norm_gate`). |
| E1n2 | `p90_expert.hpp:92` (`Kernel<...Prefetch...>`), the `p90_layout.hpp` loader, and the expert submit in `p49d_expert_submit.cpp`. |

## Process-wide selection: the required pattern (avoid the p58asc mistake)

**The mistake.** In p58asc, the one-card spin wait was reachable only through
`view.hc == spin` in the bracket table. Chain windows (KD/W2m/WS) could not
express it, so the binary was rebuilt twice. p58asd fixed it with a
process-wide `--wait-policy poll|spin` that defaults to the parent. Its gate,
`packet58as-onecard-spinwait/wait_policy_gate.py`, is the template.

**Two-card precedent.** The two-card equivalent is `--host-path`. It is
declared once natively, emitted unconditionally with its default by the chain
pipeline, and needs no bracket.

Every candidate flag (`--warm-ahead off|dense`, etc.; default `off` = bundle 8)
must touch all of the following sites:

1. **Native option**:
   * add the field to `struct Options` (`main.cpp:133-155`), defaulting to the
     parent behaviour;
   * add a parse branch next to `--host-path` at `main.cpp:183`. Unknown
     options already throw at `main.cpp:229-230`.
   * add a value check in the require block (`main.cpp:232-262`);
   * apply it once, at Engine startup, next to the sealed-selection consumers
     (`main.cpp:716-728`), never only in a view switch. The v5 switch handler
     calls the same setter. Refuse a CLI value that conflicts with a bracket
     view, as p58asd did. `selection.json` and its SHA
     (`e617a20a…`) stay bundle 8's; the flag value is recorded in the
     window identity and receipts instead.
2. **W0p/W2m/WS/WSs/WS128x/WS128**:
   * add `p.add_argument('--warm-ahead',choices=('off','dense'),default='off')`
     to `chain_pipeline.py:569-590`;
   * emit `cmd += ['--warm-ahead',args.warm_ahead]` for **both ranks** in
     `chain_pipeline.py:298-316`, next to line 310 (`--host-path`), and the
     same in `pipeline.py:310`;
   * in `window.py`: add the argument to the parser at `window.py:393`, copy it
     at `window.py:566-567` (`args.warm_ahead=a.warm_ahead`), and add it to
     the window identity at `window.py:453` and to the resume fields at
     `window.py:190`.
3. **KD**: append the flag to both draft-capture commands, the host reference
   at `draft_window.py:120-127` and the device owner at
   `draft_window.py:168-171`. They do not go through `chain_pipeline`.
4. **K1a/K1b/K2** run fixture binaries, not `own-rt-iq3` (`window.py:271-272,
   299-307`). Their parsers **throw on unknown arguments**
   (`p49d_fixture.cpp:157`, `fixture_driver.cpp:161`).
   * For a kernel-changing lever (D1, N3, G1, R1, E1n2), add the flag (default
     off) to the affected fixture binaries. Pass it from `window.py:299-307`
     so that K1 proves the candidate bytes and K2 times them.
   * For D2, which does not change values, add it to the fixtures of the
     predecessor kernels so that K1 proves the outputs are unchanged.
   * Never pass the flag to a fixture binary that does not parse it.
5. **Argv and receipt checks**: update `arguments136.py:74` (the per-window
   argv assertion) and `packet56_submission.py`, which validates window
   commands and receipts. The flag must appear in every timing window's
   recorded command.
6. **Gate**: copy `wait_policy_gate.py`. It checks:
   * byte equality for flag absent / off / on (GNU and Intel host builds);
   * parsed values in the real argv of every window (K1a, K1b, K2, KD, W2m, WS,
     WSs, WS128x, WS128);
   * that the old binary refuses the flag;
   * that a bracket conflict is refused.

## Pre-staged base

`base/` is a `git archive` of committed HEAD's `packet136-record-bundle`. See
`base-lineage.json` for the commit and file count. Its only tracked symlink,
`oracle`, is re-pointed to the same target (`../../packet49-integrate/oracle`)
and is never dereferenced. Build outputs (`build/`) are not tracked. A
candidate rebuilds only through `ops/compile_turn.py`.
