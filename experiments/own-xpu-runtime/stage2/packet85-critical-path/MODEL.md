# Packet 85: measured critical path of the two-card record line

Analysis only, October 17, 2026. No device work, service, build, settings change,
model payload read or external submission. Existing packet, screen and ops
trees are inputs only. This packet does not change a runtime or qualify a record.

The useful model is **draft plus the slower target half on hits; restore and
the corrected first half plus the slower target half on misses**. Drafting on
rank 1 overlaps miss repair. Moving the draft to rank 0 removes that overlap.
It does not remove drafting from the hit path.

The model gives **53.984 tok/s**, against **54.064 tok/s** measured in packet
77's control: −0.080 tok/s, or −0.148%. Its hit/miss paths are **16.046/27.701
ms**. Command-cost accounting gets every requested experiment's sign and size
right, but that is a retrospective check. Transferring measured component
savings from lane A to held-out lane B predicts wide64, HC-wide and ordered
cleanup with errors of **+0.854, +0.299 and +0.146 percentage points**.

This does **not** establish a way to predict an unseen kernel's device time
from its bytes or static instruction count. The older sparse expert tables
underpredict wide64's gain; device-only M=2 costs badly underpredict depth two's
loss. Those errors are retained below. A forecast without a defensible new
component cost must stay conditional, rather than becoming another promised
gain.

## Evidence, identity and definitions

Primary evidence is [packet77 control and raw events][p77], including each
prompt's `receipt.json`, `rank_trace`, `draft_rows`, host `timings.jsonl` and the
paired instrumented `sites.jsonl`. The record selection is packet70 wide64,
draft-HC and batched rollback, **24/24 layers, draft on rank 1**, arithmetic
`iq3-p49-split32-v1`, full BF16 KV. Packet76's shared wrapper uses **23/25**;
these configurations must not be silently interchanged.

[model.py](model.py) joins commands by rank, operation, position and speculative
flag. Trace list order is wait/collection order, not a single serial execution
timeline. All dependency times use the shared host monotonic clock. GPU events
are used only within their own card for attribution. Transfers with zero-width
copy timestamps are **unknown**, not free.

The baseline uses the first **99 emission intervals** of each of 12 prompts:
1,188 intervals, 936 hits and 252 misses. A hit/miss labels the guess verified
at the **starting emission**, which determines the work before the next one.
One interval produces one verified token. There is no `1 + acceptance`
multiplier for this depth-one pipeline. Packet77's full-128 summary reports
16.077/27.708 ms as medians of per-prompt means; the first-99 conditional means
here are 16.046/27.701 ms. Neither definition is substituted for the other.

For sensitivity, `p = 100/127 = 0.787402`, the requested median acceptance.
The pooled first-99 acceptance is 0.787879. A pooled expected-time model and a
median of six prompt-class medians need not agree exactly. Comparisons below
retain the declared class-balanced first-99 metric and matched controls.

## Dependency chains

The measured command means below come from uninstrumented control traces.
`A` is speculative rank0 work, `C` is corrected rank0 work, and `B` is rank1
target work. A speculative half includes state capture and speculation-specific
housekeeping; it is not interchangeable with the cheaper corrected half.

| Component | Mean ms | Scope |
| --- | ---: | --- |
| `A`, speculative rank0 half | 13.688 | Every speculative target step |
| `Bh`, rank1 half following a hit | 14.232 | Target layers, head, final norm, argmax, host work |
| `Bm`, rank1 half following a miss | 14.463 | Keep the measured miss-conditioned difference |
| `D`, draft command | 1.795 | Host receipt through completion, including publication work |
| `R`, rollback **including restore** | 0.569 | Misses only; no independent restore timer |
| `C`, corrected rank0 half | 12.655 | Misses only |
| `Gh` / `Gm`, remaining control gaps | 0.020 / 0.013 | Signed residual after dependency accounting |

**Hit, from verified emission `t[n]` to `t[n+1]`:**

```text
rank1 final hidden state / verified token at t[n]
  -> rank1 draft D = 1.795
  -> rank0 output handoff, mailbox and half-input ordering
  -> [rank1 target Bh = 14.232 || next rank0 speculation A = 13.688]
  -> verified emission t[n+1]

rank0 accepts the already-completed correct speculative state while D runs.
H = D + max(Bh, A + start_offset) + Gh = 16.046 ms
```

**Miss:**

```text
rank1 final hidden state / verified token at t[n]
  -> [rank1 draft D = 1.795
      || rank0 rollback+restore R = 0.569 -> corrected half C = 12.655]
  -> accept corrected state -> rank0 output handoff to rank1
  -> [rank1 target Bm = 14.463 || next rank0 speculation A = 13.688]
  -> verified emission t[n+1]

M = max(D, R+C) + max(Bm, A + start_offset) + Gm = 27.701 ms
```

The speculative half being verified is already complete when these intervals
start. It ran beside the **previous** rank1 half; adding it again would double
count it. The next speculative half races the next rank1 half and is included
in `max`, not summed. The mean signed start offset is −0.000400 ms; it is
retained in the calculation.

```text
T = p H + (1-p) M = 18.524 ms per verified token
rate = 1000 / T = 53.984 tok/s
```

Handoff evidence is small but cannot identify individual DMA costs:

| Host-clock boundary | Mean ms | Interpretation |
| --- | ---: | --- |
| Emission to draft receipt | 0.00547 | Accept, controller/mailbox/issue |
| Emission to rollback receipt, misses | 0.00549 | Starts alongside the draft |
| Restore completion to corrected-half receipt | 0.00123 | Serial miss-path control |
| Later ready branch to rank1-half receipt | 0.01162 | Includes accept, handoff and mailbox ordering |
| End of target/speculation race to emission | 0.00106 | Completion collection |

These boundaries explain the small gaps; do not add them again to `Gh/Gm`.
Input/output copies inside a half remain in that half. The multi-millisecond
rank0-finish-to-rank1-start field in older receipts includes waiting for the
other branch and the draft, so it is not a multi-millisecond memcpy.
`rank.hpp` and `native_controller.hpp` establish the restore, draft and handoff
dependencies; their hashes are in the input manifest.

## Outside layers and the limits of the bandwidth tables

Packet77's **instrumented**, paired rank1 accounting is:

| Part | ms |
| --- | ---: |
| First-layer start through last-layer end | 11.962 |
| Target head | 1.404 |
| Final norm/merge | 0.052 |
| Argmax | 0.023 |
| Host wait/submission/gaps/unattributed remainder | 1.544 |
| Whole sampled host command | 14.984 |

This instrumented sum is not substituted for the uninstrumented `B`.
The head reads 794.6 MB of useful expanded bytes at about 566 GB/s; the
allocation is larger because it retains source metadata. [Packet69][p69]
corrected that distinction. The draft's current raw event breakdown is prefix
0.521 ms, attention 0.387, HC 0.251, experts 0.251, embedding 0.060, shared
expert 0.044 and argmax 0.021. These event buckets are inside `D`, not additions
to it. Packet69's older draft-HC cost of about 0.328 ms is not today's cost.

[Packet76's host audit][host] finds 0.666 ms of uninstrumented housekeeping
versus 1.457 ms observed with instrumentation, and only 0.00125 ms of measured
gaps after the final layer. Its roughly 3.03 ms enqueue loop overlaps device
execution. There is no evidence for recovering the entire 1.544–1.608 ms
remainder, nor for adding the whole enqueue duration to the critical path.

[Packet72][band] and packet77 sample layers 22/23 and 24/27 and scale site costs
by occurrences. Their per-half tables are **estimates from measured calls**;
unsampled layers are not measurements. The 555 GB/s reference excess is not an
achievable speedup, especially for lookup, reduction, launch or dequantization
limited kernels. No DRAM transaction counters were captured.

## Sensitivity and slack

The entries are the change in **overall expected tok/s** if 0.1 ms is removed
from that component on the indicated path, at fixed acceptance. The two
columns therefore include hit/miss frequency. They are not changes in the
all-hit or all-miss rate. `model.json.site_sensitivities` supplies the same
mapping for every packet77 site.

| Component saved by 0.1 ms | Hit-path contribution, tok/s | Miss-path contribution, tok/s | Both paths together |
| --- | ---: | ---: | ---: |
| Rank1 target component: expert, HC, route, recurrence, head, exposed host work | +0.2304 | +0.0620 | +0.2930 |
| Rank0 speculative half, including its capture | 0 | 0 | 0 |
| Rank0 corrected half or one of its components | 0 | +0.0620 | +0.0620 |
| Rollback/restore | 0 | +0.0620 | +0.0620 |
| Draft, including prefix, attention, HC, experts or exposed draft host work | +0.2304 | 0 | +0.2304 |
| Same kernel saves 0.1 ms in each target rank | +0.2304 | +0.1242 | +0.3557 |
| Exposed handoff/control work on just that path | +0.2304 | +0.0620 | Depends on which boundary changes |

The last row is a normalized sensitivity, not a claim that the measured
0.020/0.013 ms gaps contain 0.1 ms to remove. Likewise the final norm and argmax
are smaller than 0.1 ms. Savings are capped by actual component cost.

Rank0 has **0.544 ms mean hit-path slack**; individual first-99 samples have
0.262–1.121 ms slack across both path classes. Making speculative rank0 faster
alone has zero local value. Making rank1 faster eventually consumes that slack,
after which rank0 matters. The draft has **11.430 ms of miss-path slack** behind
restore plus correction. Saving draft time does not shorten these misses.
The derivative changes at either crossover; scenario gains must be recomputed
with `max`, not added indefinitely.

Although rank1 owns the draft, do not balance `A` against `B+D`: `D` precedes
both next-half launches. At 24/24 the relevant half imbalance is only about
0.54 ms. That is why a blanket move of several target layers is unsupported.

## Validation, including failures of the earlier projections

The first table supplies each run's **measured command durations**, follows the
dependency graph without fitted rate coefficients, omits the tiny unmodeled
control gaps, and predicts the class-balanced first-99 rate. It verifies the
accounting and explains signs; it is **not a blind forecast of kernel speed**.
Controls are the arithmetic mean of the two bracketing rates, including the
second packet79 control. All inputs and command identities are hash-listed.

| Experiment | Model change | Measured change | Error, percentage points |
| --- | ---: | ---: | ---: |
| p65 wide64 A | +5.386% | +5.385% | +0.000 |
| p65 wide64 B | +4.807% | +4.796% | +0.011 |
| p73 HC-wide A | +0.975% | +0.976% | −0.000 |
| p73 HC-wide B | +0.733% | +0.731% | +0.002 |
| p76 ordered A | +1.056% | +1.053% | +0.003 |
| p76 ordered B | +0.410% | +0.409% | +0.001 |
| p74 head-packed | −0.799% | −0.770% | −0.029 |
| p74 dense-packed | −2.403% | −2.369% | −0.034 |
| p74 combined | −2.957% | −2.924% | −0.033 |
| p79 draft rank0, 23/25 | −2.109% | −2.128% | +0.020 |
| p79 draft rank0, 24/24 | −1.114% | −1.120% | +0.006 |

The brief's packet79 −2.3%/−1.3% compares against its **first** 54.106 tok/s
control. The second was 53.910; using both changes the reference, not the
conclusion. Packet76 A is +0.450% against its first control but +1.053% against
both; its B confirmation is +0.409%. Keep these drift differences visible.

For a stronger check, take lane A's component savings, hold them fixed, apply
them to lane B's controls, then compare with the withheld B candidate:

| Candidate | A-cost model prediction on B | B result | Error, percentage points |
| --- | ---: | ---: | ---: |
| wide64 | +5.650% | +4.796% | +0.854 |
| HC-wide | +1.029% | +0.731% | +0.299 |
| Ordered cleanup | +0.555% | +0.409% | +0.146 |

No B candidate duration enters those predictions. This is transfer of a
measured mechanism, still not pre-build prediction. A separate temporal test
fits each packet77 prompt's first 48 intervals, then predicts its remaining 51
using only their hit counts. Errors are +0.31% to +0.89%, all optimistic: early
costs understate later costs. Small expected gains need matched repeat evidence.

**Draft placement can be rejected structurally.** Keeping packet77's costs
fixed and serializing `D` with `R+C` predicts **−2.018%**, even before pricing
the additional reverse handoff. Against the brief's first-control losses the
errors are about +0.29 percentage points (23/25) and −0.72 (24/24). Actual hit
times move slightly and misses grow about 2.1 ms. The source requires rank1's
final hidden state before drafting; relocation cannot make it independent.
[Packet45 SPEED4][restore] had already separated exposed rank0 draft time from
restore time. The [submission ledger][ledger] records SPEED3 at 38.157 and
SPEED6 at 39.422 tok/s, but those also differ in split/restore configuration;
their 3.2% difference is corroborating history, not a matched placement effect.

**Depth two needs a different graph and token denominator.** Its controller
does `op19` (fresh draft plus two recursive passes and draft-state backup/restore),
then optionally rebuilds rank0's current tile, races rank1's current tile with
rank0's future tile, and finally commits or discards/restores. The source's
`op17` feedback pass precedes the second emission on an accepted second row.
The `hit_miss_cycle_statistics` for p71c are decisions per tile, not one emitted
token per row; feeding them into the depth-one formula is invalid.

| Depth-two command/branch | Measured mean ms |
| --- | ---: |
| Three-pass proposal plus private backup/restore (`op19`) | 8.022 |
| Rank0 current-tile rebuild, when required | 31.955 |
| Rank1 current tile | 31.692 |
| Rank0 speculative future tile | 32.498 |
| Confirmed draft feedback (`op17`), when required | 1.604 |
| Rank0 select/restore command | 1.094 |
| Rank1 select/restore command | 1.044 |
| Future discard (`op18`), when required | 0.047 |

There are 881 tiles, 449 current-tile rebuilds, 868 future tiles and 633
feedback passes across the 12 requests. Restore/select commands have position
zero in the trace; the reproducer assigns them by time, not token position.
Summing serial work and taking `max` only for the genuinely concurrent tiles
gives **28.581 tok/s**, versus **28.573** measured over all 127 intervals:
+0.008 tok/s. Against the matched full-decode control, predicted/measured loss
is **−46.097%/−46.112%** (error +0.015 percentage points). The requested
first-99 result is **28.165 versus 52.899**, or **−46.758%**. Comparing the
full-window prediction to that first-99 change incurs +0.787 percentage points
of error and is explicitly a window mismatch, not an exact prediction.

Two less successful forecasts matter more than the near-exact replay:

* The packet72→77 sampled expert tables imply only **+2.565%**, versus p65 B's
  **+4.796%**: **−2.231 percentage points** error. They sample two layer types,
  use different sessions and omit full command effects. Do not inflate their
  sampled delta to match the endpoint or claim all layers were measured.
* Use p68c's device-only H2 times 21.89/23.03 ms, p68's 0.981 ms restore, three
  draft passes, unchanged `p`, independent guesses (`rebuild ≈ 1-p²`) and
  `1+p` emitted tokens per tile. That already predicts **−16.594%**, not +11%,
  but misses p71c's loss by **30.164 percentage points**. Actual complete tile
  commands are about 32 ms, the recursive proposal costs 8 ms, rebuilds occur
  in 51% of tiles, and reported acceptance falls to 0.708. These missing costs
  prevent a reliable pre-build magnitude forecast. The older evidence was
  enough to reject an expected win, not enough to forecast −47% precisely.

Packed reads have the same identification problem. A byte-only model would
predict a gain; register unpacking adds work on the critical half. The retained
complete-command costs predict the observed −0.8% to −2.9%, and packet9/10/25
already supply negative mechanism history. There are no per-instruction
latency/counter measurements from which this packet can honestly predict the
exact unseen unpack penalty. Packet81's subsequent neutral load-count reduction
is another reason not to equate fewer loads with lower critical-path time.

## Six remaining levers, ranked by evidence and useful engineering scope

All gains below are **conditional model budgets**, not new measurements,
confidence intervals, or sums of bandwidth excess. They use the packet77
baseline except the explicitly different 23/25 comparison. Engineering times
are estimates for focused implementation and gates, not device reservations.
Existing qualified gains may already be in a proposed record bundle.

| Rank | Lever and mechanism | Evidence/headroom | Assumed saving and predicted gain | Size |
| ---: | --- | --- | --- | --- |
| 1 | Smaller target-kernel launch/reduction work: HC/route; separately recurrence | Rank1 HC gates/norms/route cost 1.198/0.409/0.472 ms; reference excess 0.877/0.404/0.472 ms. Recurrence costs 0.628 ms, excess 0.576 ms | Saving 0.10–0.25 ms per target half: **+0.356–0.898 tok/s (+0.66–1.66%)**. Separate recurrence 10–25% scenario: +0.224–0.563 tok/s | Small/medium, 1–3 days |
| 2 | Cheaper draft head/prefix on rank1 | D 1.795 ms; prefix 0.521 ms, already about 561 GB/s | Saving 0.10–0.30 ms at unchanged acceptance: **+0.230–0.697 tok/s (+0.43–1.29%)** | Small/medium, 1–2 days with packet83 |
| 3 | Expert dequantization dependency/ALU work, not another load-count sweep | Gate/up+down 2.729/2.754 ms; reference excess 1.876/1.901 ms, not a promised recovery | Saving 5–15% of these costs: **+0.490–1.498 tok/s (+0.91–2.78%)** | Medium/large, 3–5 days |
| 4 | Miss restore/setup and corrected rank0 half | R 0.569 ms, C 12.655 ms; only about 21.3% of intervals pay them | Save R 0.10–0.30 plus C 0.30–1.00 ms: **+0.249–0.818 tok/s (+0.46–1.51%)** | Medium/large, 2–5 days |
| 5 | Exposed host cleanup/issue | Only 0.666 ms control housekeeping in p76 is identified; p77's 1.544 ms residual is instrumented/unresolved | Save 0.05–0.15 ms serial rank1 work: **+0.146–0.441 tok/s (+0.27–0.82%)** | Small/medium, 1–2 days |
| 6 | Keep draft on rank1; compare 24/24 with 23/25 only where the latter remains | Layer23 sample totals 0.505 ms; current hit slack 0.544 ms | Moving that layer off rank1: **+1.135 tok/s, +2.15% relative to modeled 23/25**. Zero additional gain on packet77, which is already 24/24 | Small, 0.5–1 day |

**Prior attempts and lossless constraints for each:**

1. HC-wide has a measured +0.731% B confirmation. Packet78 route-fast is
   +0.538% on A and small+hc-wide is +0.510% on B; the JSON retains both raw
   comparisons. Norm-fused alone loses 0.650% and small-combined loses 0.387%
   on A. Do not call a losing norm kernel a win because a combination contains
   a faster HC kernel. [Packet78][p78]
   identifies about 3.2/3.2/10/3.3 µs in its four route stages. [Packet67][dnr67]
   closes four-stream HC and the separate recurrence shared-head prepass;
   [packet82][dnr82] proposes a different in-kernel sharing mechanism. Preserve
   reduction trees, norms, top-k/tie order, BF16 boundaries and recurrence
   state. Do not reopen the spilled HC geometry or turn the reference excess
   into a multi-percent forecast. HC, route and recurrence savings need their
   own measured component deltas before combination.
2. [Packet69][p69] closed wider head and draft-attention/HC geometry below the
   promotion bar. [Packet79][dnr79] closes relocation. [Packet83][dnr83] already
   prepares independently selected shorter prefixes and draft-only Q4. The
   draft may change; the target weights/arithmetic, verifier and BF16 KV may
   not. A 0.20 ms draft saving breaks even after only **1.33 percentage points
   of acceptance loss**; 0.10/0.30 ms tolerate only 0.67/1.98 points. Prefixes
   must not be chosen from benchmark answers. Acceptance and time must be
   measured together; target quality alone does not prove a speed win.
3. [Packet65][dnr65] wide64 worked; p73 experts2 did not. The new [packet81
   closeout][p81] is neutral despite reducing static loads 51→27 and 79→31.
   This closes that load-count mechanism; it does not by itself prove the
   precise hardware stall cause. IQ2 grid/dequant dependency is a hypothesis.
   [Packet81 boundaries][dnr81] also keep SLM/persistent/free-order/V16
   repetitions closed. Preserve independent gate/up metadata, per-lane FP32
   accumulation and final BF16 rounding. Require a genuinely different
   decode/latency mechanism before building another full engine arm.
4. [Packet45 SPEED4][restore] already omits proved spare-bank restoration for
   confirmed redo, and packet64/70 already batch rollback. These are not new
   levers. `A-C ≈ 1.03 ms` is not an isolated copy measurement. The entire
   0.569 ms rollback removal would be only about +0.36 tok/s; most miss upside
   would need a cheaper corrected half. Any new omission needs an overwrite
   and ownership proof including metadata, abandoned redo and observable
   terminal state. No masked state hashes, speculative output, response reuse
   or compressed cache. [Depth two][p71] remains closed without a different
   verify structure, not merely a more optimistic tile estimate.
5. [Packet76][host] already tested ordered event retirement. Its B gain is
   only about +0.41%; do not count it again if present in the composed line.
   Generic graph replay remains unsupported by these sampled gaps. Preserve
   completion/error semantics, synchronization and graceful teardown.
   Earlier enqueue times do not establish serial host stalls; a new issue
   mechanism needs per-submit evidence before receiving a speed budget.
6. [Packet45 boundaries][dnr45] retain split/memory history; [packet76][dnr76]
   explicitly uses 23/25 and [packet77][p77] measures 24/24. The packet80 note
   also selects rank1 drafting at 24/24. Thus this is a check against accidental
   regression in a composed configuration, not a new gain to add to the record.
   Preserve every target operation and admission reserve. Do not reuse p79's
   rank0-draft choice, or move extra layers merely because rank1 owns `D`.

The searches cover every `stage2/*/DO-NOT-REPEAT.md`,
`notes/2026-10-1[5-7]*` (excluding this packet's own new note), and
`results/localmaxxing-submissions.md`. `model.json.prior_art_search` retains
matching paths, line numbers and text; the complete read inputs are hashed.
Some original DNR rows still say “CPU pending” while later notes/raw receipts
contain device outcomes. This packet records that evidence precedence without
editing those frozen files. Packet81's 23:15–23:38 UTC result is included;
packet82/83 device verdicts remain pending in this evidence snapshot.

## Decision rule for the next proposal

Use the dependency graph first. State which command changes, whether its
saving is exposed on hits, misses or both, the new work/dependencies it adds,
and the acceptance change it can afford. Use complete command timings from a
matched mechanism when available. Otherwise report a conditional budget and
the missing cost explicitly; no positive point prediction from bytes, load
counts, an ideal tile or the 555 GB/s reference alone.

For this line, keep rank1 drafting and depth one. Check the split of the
composed line, carry forward the measured small-kernel wins without double
counting, and require a new ALU/latency explanation for expert work. This is
the analysis recommendation; packet85 schedules or implements none of it.

## Reproduction and retention

From the repository root:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/stage2/packet85-critical-path/model.py </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/stage2/packet85-critical-path/model.py --check </dev/null
```

The standard-library script enforces a 4 GiB address-space ceiling, reads only
the named repository evidence and writes only its adjacent `model.json`.
`--check` writes nothing and requires byte-identical recomputation. Raw packet77
event/timer hashes are also checked against their attribution manifest.
There are no imports from runtime workers, no device discovery, and no model
payload access. The JSON contains equations, measured components, source
hashes, all per-site sensitivities, validation errors, held-out checks, ranked
levers and explicit assumptions for every scenario. `MODEL.md` is the reviewed
interpretation rather than generated runtime code.

**Local evidence dependency:** the referenced screen run trees, including
packet77's attribution JSON, are ignored/untracked in this checkout. A clean
Git clone alone cannot run this analysis. Preserve those trees at the exact
paths/hashes in `model.json.source_sha256`; obtain that evidence snapshot before
recomputing elsewhere. No raw evidence is moved, edited or discarded, and this
packet makes no public-recipe reproducibility claim. Changes in source evidence
or searched notes intentionally make `--check` fail rather than silently using
different inputs.

[p77]: ../screen/v4-lanes/evidence/packet77-attribution-B-a/run/
[p69]: ../../../../notes/2026-10-17-own-runtime-packet69.md
[p71]: ../../../../notes/2026-10-17-own-runtime-packet71c.md
[p78]: ../../../../notes/2026-10-17-own-runtime-packet78.md
[p81]: ../../../../notes/2026-10-17-own-runtime-packet81.md
[host]: ../packet76-rank1-host/ATTRIBUTION.md
[band]: ../packet72-occupancy/BANDWIDTH.md
[restore]: ../packet45-merged3/SPEED4-CLOSEOUT.md
[ledger]: ../../../../results/localmaxxing-submissions.md
[dnr45]: ../packet45-merged3/DO-NOT-REPEAT.md
[dnr65]: ../packet65-expert-occupancy/DO-NOT-REPEAT.md
[dnr67]: ../packet67-roofline/DO-NOT-REPEAT.md
[dnr76]: ../packet76-rank1-host/DO-NOT-REPEAT.md
[dnr79]: ../packet79-draft-rank0/DO-NOT-REPEAT.md
[dnr81]: ../packet81-experts3/DO-NOT-REPEAT.md
[dnr82]: ../packet82-recurrence/DO-NOT-REPEAT.md
[dnr83]: ../packet83-draft-bytes/DO-NOT-REPEAT.md
