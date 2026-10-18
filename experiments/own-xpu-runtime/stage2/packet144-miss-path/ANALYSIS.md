# Packet144 — shrinking the two-card wrong-guess penalty

| Rank | Exact mechanism assessed; what would change | Projected in-engine gain, assumptions and transfer evidence | Implementation size / risk | Overlap and decision |
| --- | --- | --- | --- | --- |
| 1 | **Correction-only cooperative rows/experts:** after a miss, rank1 executes disjoint output rows or selected experts from rank0's corrected half. Return results to their original slots; retain every per-row reduction and the original expert-combine order. Ordinary hit placement stays 24/24. | The only assessed new direction with enough potential work: C is **11.819 ms**. It needs **2.338 ms net per miss** for +3%. A hypothetical 3 ms raw reduction at 20% transfer gives about **+0.75%**, versus **+3.88%** at perfect transfer. Neither 3 ms nor perfect transfer is established. Packet128b identifies attention/HC/MoE work, but supplies no cooperative-correction timing. There is **no supported ≥3% projection**. | Large: roughly 1–2k new lines plus gates; new per-layer exchange, weight admission, private output/state ownership and failure protocol. Rank1 initially runs D. Remote weights, extra traffic and reductions can erase savings; device capacity is unproved. | Distinct from packet120's static placement and packet79's draft relocation: removes rank0 correction work only. It does not evade their saturation evidence. Also distinct from packet132: no second guessed candidate. **Do not implement without new transfer/memory evidence.** |
| 2 | **Miss-window rank1 prefetch:** warm only immutable bytes needed by rank1's forthcoming target half while rank0 performs C; stop before target work. This is cache preparation, not prompt/KV reuse. | Even granting removal of **all B on misses**, unchanged rank0 A leaves only **+0.916%** in bundle8's measured interval model. Real prefetch saves less, may cost time, and has no demonstrated cache residency/traffic benefit. This bound grants more than any prefetch could achieve. | Medium: 150–400 lines plus cache/traffic probes; synchronization and cache pollution risks. All next-layer selected experts are unknown before that layer's router. CPU LLC warming is not proof of device-cache residency. | Different scheduling window from packet119's in-kernel DOWN warming, but that exact negative was **1.079× slower**. Packet138 predicted expert prefetch also failed; no importing its optimistic assumptions. **Below gate even at an impossible bound with A unchanged.** |
| 3 | **Exact early loser witness:** compute the guessed head row and another row with an exact higher value (or lower-ID equal-value winner), then begin token-independent restoration before global head completion. Finish all rows and finite checks. | A loser witness proves “miss,” **not the corrected token**. Without earlier winner availability or cancellation of unfinished A, only R can be hidden: **≤+0.691%**, granting zero witness/handshake cost and full exposure of all R. Actual partial-head readiness is unmeasured. | Medium/large: 300–800 lines plus adversarial tie/error/cancellation tests; new miss-only message and restoration state. Existing redo requires the verified actual token. | New early-miss protocol, not packet130's suffix interleave. Advancing the whole suffix or cancelling A re-enters packet130's dependency question and needs new evidence. **Below gate in its independently exact scope.** |
| 4 | **Layer-local restore/first-use scheduling:** restore each remaining mutable extent before its first corrected consumer; overlap later restores with early C on a separate queue, preserving all terminal and abandoned-redo state. | Maximum is again all R: **≤+0.691%**. Even granting the old record's entire **0.102197 ms** correction preparation for free as well gives **≤+0.820%**. The measured R is 0.551 ms; packet128b's 0.214 ms device restore is not additional time. | Medium/large: 400–900 lines plus alias/first-use proof, queue fences and prepared-pointer audit. Shared scratch and bank parity make a simple removed drain unsafe. | Substantial overlap with closed packet121/88/62; `miss_overlap()` already has a batch-overlap path. The new element would have to be per-extent first-use dependencies. Packet136 already adopted bank rotation; do not count its capture saving again. **Closed below gate.** |
| 5 | **Stream the corrected boundary in canonical tiles:** hand off completed portions of layer23's final streams to rank1, preserving each consumer's original accumulation order. | No whole-layer overlap exists: layer24 needs layer23, not an earlier rank0 layer. Tiling could only expose the final producer tail and its consumers. If it advances B alone while A waits for C, the generous **+0.916%** bound still applies. To move A too requires earlier *completion* of C, with **2.338 ms net** required; no measured tile-tail/transfer evidence supports it. | Large: 800–1500 lines plus cross-card partial-result lifetimes and exact accumulator checks. Norms, gates and full-vector reductions limit early consumption; sum reassociation is forbidden. | Layer migration overlaps packet120/123; operator tiling is a distinct unmeasured mechanism, not a free layer-granular handoff. **No supported ≥3% case.** |
| 6 | **Better miss-rate discrimination without a second target half:** a new deterministic draft correction/reranker, with every proposed token still checked by the unchanged target. | At zero added work, a uniform rescue of **21.71% of current misses** (about **+4.68 acceptance percentage points**) is required for +3%. No new proposer or independent acceptance evidence establishes it. Packet129's measured +0.08 points is far below this; packet132's sibling rescue paid enough extra work to fail +3%. **No positive gain credited.** | Large/open research: new draft computation and independent held-out evaluation, then full exact-target checks. A different proposer may alter draft state/latency even with identical target outputs. | Does not reopen draft quantization, prefix retuning, depth2, learned/history reuse or two-candidate speculation. Packet129/132/96 close those tested versions. **An acceptance target is not a mechanism qualification.** |
| 7 | **Use rank1 during C for the next exact draft.** | **0% incremental:** the available draft is already launched before rollback/correction. A further draft needs corrected target final streams and its next verified token, which are unavailable. Packet128b's ~1.407 ms draft runs beside C, not after it. | No implementation justified. Launching an extra draft requires private mutable state and would be speculation, not available exact work. | Explicit packet121/79/126 boundary; depth2 remains closed. **Dependency-refuted as proposed.** |
| 8 | **Skip token-independent corrected layers or replay their outputs.** | **0% proved removable layers.** Corrected embedding and PLE IDs change the first streams, then every downstream layer consumes token-dependent state. Static weights, prior committed context and bindings are already reused. A specific immutable subexpression is different; packet137 already owns token-input preparation. | No implementation justified without a concrete read-set/byte proof. Reusing wrong-token recurrent or attention output changes the model. | Explicit packet88/121 closure; no repeated model-shaped CPU reads to rediscover it. **No new exact layer reuse.** |

October 18, 2026. **Close at the +3% ranking gate.** None of these mechanisms
has both sufficient projected gain and supported transfer. No design, runtime
copy, smoke/v5 proposal, rehearsal or READY-FOR-DEVICE marker is warranted.
The table ranks research value and strength of the available bounds, not
measured candidate speed. Implementation sizes are planning estimates of new
code, excluding the vendored parent and broad test harness.

## Record identity and the actual hurdle

The current record is packet136 bundle8, **58.798108759182306 tok/s**, on two
B70 cards. It retains `iq3-p49-split32-v1`, unchanged quantized compressed
Unsloth UD-IQ3_XXS target bytes, full BF16 KV, rank1 MTP, fixed 80,128-row draft
prefix and 24/24 layers. Its device binary is
`fd7e8b6f5fb24c5042d051f59026091a9184c0f15149d7de110528b7d3ac5451`.
[Original record](../packet136-record-bundle/submission/prepared-a/result.json).
Its owner-authorized 128-token scope, false strict512 gate and missing prefill
measurement are unchanged by this analysis.

We reconstruct **all 1,188 first-99 intervals from that record's twelve saved
request receipts**, not just the older packet135 aggregate. The class-balanced
rate reproduces exactly. There are 932 hits and 256 misses: pooled acceptance
**0.784512** in this interval subset, distinct from the approximately 0.787
summary acceptance in the brief. No prompt selection or new execution occurs.

| Saved host-envelope mean, ms | Packet135's bundle7 hit / miss | Bundle8 hit / miss |
| --- | ---: | ---: |
| D, available rank1 draft | 1.609391 / 1.608345 | 1.597226 / 1.595828 |
| R, rank0 restore | 0 / 0.546061 | 0 / 0.551168 |
| C, corrected rank0 half | 0 / 11.820039 | 0 / 11.818807 |
| A, next speculative rank0 half | 12.796884 / 12.798686 | 12.482216 / 12.485768 |
| B, rank1 target including head/suffix wait | 13.275496 / 13.323167 | 13.086387 / 13.230429 |
| Complete emission interval | 14.904587 / 25.702393 | 14.704424 / 25.613427 |

Bundle8's pooled mean is 17.055185 ms; the class-balanced headline has a
different reciprocal. The calculator preserves per-prompt rates, class medians
and their median. It neither substitutes a pooled rate nor scales bundle7
times by the ratio of the records.

```text
T = max(D, R + C) + max(B, A + offset) + G
```

This is packet135's same emission-to-emission accounting, applied to each
bundle8 receipt. G is a signed reconstruction remainder, not removable idle.
The next speculative half A is already counted once. B contains suffix wait;
its subtraction must not also be claimed as rank0 savings. All command times
use a common host clock; no cross-GPU/device-host clock subtraction is used.

Changing only C in each actual interval gives **2.337708 ms per miss** for
exactly +3% (bundle7: 2.360847). This is approximately **19.8% of C**. Merely
saving 2.3 ms gives **+2.950%**, below the unchanged gate. The old 20% provisional
operator-transfer convention would require roughly **11.69 ms of raw savings**
to deliver 2.338 ms net; it cannot turn a modest copy or kernel tweak into a win.
Transfer is mechanism-specific: removing a measured serial operation may
transfer directly, whereas cooperative rows have unmeasured replacement costs.

The ideal miss-rescue calculation proportionally removes each miss's
`max(D,R+C)-D` penalty, with zero proposer cost. It gives the required 21.71%
rescue fraction / +4.68 acceptance points. Fractional rescue is a sensitivity
calculation, **not synthetic token evidence, a predicted acceptance rate, or a
benchmark point**. A real proposal must establish its own distribution across
independent prompt classes and include its cost.

## What packet128b/134 can and cannot establish

Both are source attribution, not the current record's kernel clock. Packet128b
ran 51.475451 tok/s, 0.888 of its reference, and failed its overhead gate. Its
84 sampled cycles contain 66 hits and 18 misses. Its rank0 miss classes contain
two target halves, so they must not be interpreted as C alone. Rank1 contains
one half plus draft. Its ~10.09 ms rank1 miss compute gap is dominated by
dependencies and sampling; it is not an extra removable serial budget.

Packet134 measures correction compute busy **11.355503 ms**, internal gaps
**0.085150 ms**, and restore-end→correction-begin **2.046383 ms** including
**1.941660 ms** instrumented host preparation. Packet135's ordinary bundle7
preparation was only **0.102197 ms** with zero observed major faults. We do not
credit the larger instrumented gap. Bundle8 has command envelopes in the
retained archive; a new ordinary-run preparation split is not established here.

Consequences for each table row:

- Cooperative C needs to shorten real compute, not delete the overlapping
  2.89 ms enqueue loop or use a failed-overhead profile as a speed result.
- Prefetch/streaming B cannot erase A's parallel critical branch. Even the
  calculator's impossible removal of B is less than 1% on miss intervals.
  B−A is used only for that upper-bound counterfactual, never as free head slack.
- Restore/witness work is bounded by R; packet128b's restore compute and
  packet134's host gaps are not additive to it.
- Draft work already overlaps correction. The next draft's missing inputs
  cannot be supplied by interpreting idle as available compute.
- Reuse requires identical inputs. The class census contains no proof of a
  token-independent corrected layer or a qualified acceptance improvement.

[Packet128b budget](../packet128b-attribution/BUDGET.md),
[packet134 attribution](../packet134-submission-stalls/ATTRIBUTION.md),
[packet135 analysis](../packet135-critical-path/ANALYSIS.md).

## Source proof and exactness boundaries

All anchors below refer to the frozen packet136 source, whose exact bytes are
retained in `inputs.json.gz`:

- `native_controller.hpp:91–95`: issue the available rank1 draft, then restore
  and recompute rank0 on a miss. Lines 70–71 hand over the completed streams.
- `rank.hpp:38–47,133–180`: rank ownership, corrected token preparation,
  dependent layer traversal and final stream export. Layer24 needs the
  completed layer23 streams; there is no layerwise pipeline within one token.
- `mtp.hpp:190–195,225–230`: the draft merges confirmed-token embedding with
  final target streams. One later exact draft cannot run using old streams.
- `p105_runtime.hpp:55–78`: finish the prefix and suffix, preserve finite/error
  flags, then merge the full-head winner. A partial loser witness does not name
  that winner. `rank.hpp:308–310` requires the actual token for confirmed redo.
- `strict_snapshot.hpp:316–347`: restore, overlap mode, prepared metadata and
  abandoned-redo obligations. Moving copies requires first-use fences and a
  complete terminal-state proof; removing a wait alone is not that proof.

For cooperative rows, exactness is possible only if an unchanged row kernel
receives identical input bytes on its assigned device and output slots preserve
the original combine order. Neither mathematical associativity nor matching
tokens on an easy fixture proves this. Memory fit, row invariance, full state,
miss/terminal/reset cases and fresh-process equality would all precede speed.
These obligations are reasons no implementation is admitted, not a new design
or request for a device window.

## Closed-packet audit and reproduction

Before opening any arm, the repository-wide grep covered **176 existing
DO-NOT-REPEAT files**. Their full text and hashes are retained in
`inputs.json.gz`; matching lines are in `model.json:negative_index_matches`.
This includes packet132's **+2.25% / +1.77% held-out failure of +3%**; the gate
is not lowered. Packet121, 62, 88, 79, 120/123/127/130, 126, 129, 119/138 and
140 are explicitly accounted for. Existing packet trees, shared screen code,
ops files and live queues remain frozen.

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/stage2/packet144-miss-path/analyze.py --check </dev/null
```

The script has a 4 GiB address-space cap and only standard-library imports.
It reads tracked receipt archives and the retained source/negative-index
snapshot, verifies hashes, reconstructs both records and checks the saved
calculation byte-for-byte. It imports no runtime and reads no model or
full-shape data. No build is necessary. These checks validate analysis, not
candidate quality or speed. No external technique or library was adopted.

[Work note](../../../../notes/2026-10-18-own-runtime-packet144.md).
