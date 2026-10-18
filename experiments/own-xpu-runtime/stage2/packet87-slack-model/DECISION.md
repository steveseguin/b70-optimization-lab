# Packet 87: splitting heads across the two ranks — closeout

<!-- campaign-closeout -->

## Question and identity

Can the record configuration give rank 0 some target-head rows, or some draft
prefix rows on hits, without making misses slower? CPU model check,
2026-10-18 UTC, within the requested 30-minute box. No engine implementation.

The reference is packet77's packet70 wide64 control: **24/24 target layers,
draft on rank 1, `iq3-p49-split32-v1`, BF16 KV**. The model uses packet85's
unchanged [`model.py`](../packet85-critical-path/model.py), recomputes its
components from packet77's 12 control receipts, and retains its acceptance
assumption `p = 100/127`. Each interval emits **one** verified token.

**Baseline correction:** packet85's quoted **54.063896 tok/s** is read from
packet77's root `run/summary.json`, whose requests say
`attribution_arm="attribution"`. The matching uninstrumented
`run/control/summary.json` and the 12 raw control receipts give
**54.106529 tok/s**. Packet85's component model gives **53.983986 tok/s**.
That is a 0.2265% model underestimate against the actual control, not a new
regression. Existing packet85 files remain frozen. Both source identities are
retained in [DECISION.json](DECISION.json).

## Outcome

**Close out as inconclusive for sealing. Neither option is seal-ready from
these receipts.** Both have mathematical upside, but packet77 does not identify
the latency of the new device-to-host and host-to-device copies. Charging only
the measured host handoff boundaries would hide those additional costs.
This is not a finding that splitting rows is slow or that the lane is finished.

The following are **optimistic conditional forecasts**, with the measured host
boundary charges included, but the separately listed unknown DMA/merge costs
set to their lower bound of zero. They are not complete transfer-cost forecasts
or measurements. Head time is assumed proportional to rows at the current
bandwidth on either card; each local argmax still pays its entire old cost.

| Option | Rank 1 rows `[0,k)` | Rank 0 rows `[k,N)` | Hit ms | Miss ms | Model tok/s | Versus measured control |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Original packet85 model | Full head | 0 | 16.046348 | 27.700544 | 53.983986 | −0.2265% model error |
| Target head, both paths | **201,728** | **46,592** of 248,320 | **15.807279** | **27.461475** | **54.689808** | **+1.0780%** |
| Draft prefix, hits only | **46,080** | **45,312** of 91,392 | **15.813550** | **27.700544** | **54.523528** | **+0.7707%** |

Relative to packet85's modeled baseline, the counterfactual gains are +1.3075%
and +0.9994%. Against the brief's 54.063896 figure they would be about +1.158%
and +0.850%; the table instead uses the correctly matched control.

The script searches every nonempty 256-row-aligned split and includes the
untouched no-split choice. These are the optimal `k` values for **packet85's
expected-time objective under the stated lower-bound costs**, not unconditional
device optima. The continuous optima are 201,705.76 and 46,176.01 rows. Unknown
transfer costs change the optimum, especially for the draft.

## What worked

### Transfer and synchronization accounting

Recomputed from the 1,188 first-99 intervals in packet77 control receipts:

| Existing host-clock boundary | Mean ms | Charge for the proposed protocol |
| --- | ---: | --- |
| Later ready branch → rank1-half receipt | 0.011619987 | One hidden-ready publication and one result-return publication |
| Emission → draft receipt | 0.005470360 | One added rank0 head issue |
| Race completion → emission collection | 0.001062173 | One added final join/merge collection |

Thus the **additional host-boundary proxy** totals **0.029772507 ms** per
split operation. These are measured existing boundaries reused as estimates
for the new notifications, not measurements of a protocol that does not exist.
The old `Gh/Gm` stay in the model; none of their existing work is removed or
charged again as an existing operation.

Define three new serial budgets in milliseconds:

```text
E = 0.011619987 + u_export    rank1 hidden export and ready publication
I = 0.005470360 + u_import    rank0 input upload and head issue
V = 0.012682160 + u_return    rank0 result readback, publication and merge
```

The nonnegative `u_*` terms cover the **unmeasured** DMA, waits and incremental
merge work beyond those host proxies. They are `null`/unknown as evidence;
zero is used only in the explicitly optimistic scenario.

Each split needs:

1. Finish rank1's existing normalization. Export its **exact 2,560-element
   BF16 `final.mix` vector (5,120 bytes)** to host staging, then import it on
   rank 0. This is two DMA legs, one cross-rank ready notification and one
   rank0 issue. Do not recompute normalization on rank 0. The target's four
   HC streams are 20,480 bytes, but transferring those and redoing the norm
   is unnecessary for a head-only split. The draft split transfers the draft's
   own normalized vector, not the target's final streams.
2. Each rank computes its rows and its local maximum. Rank 0 returns the
   winning **BF16-rounded logit value, global index and finite/error status**
   to the controller (one result DMA, a second notification and a join).
   A compact 16-byte result payload suffices before transport sequence
   metadata. Merge on the CPU where rank0's controller already receives the
   target reply; no final token upload to rank1 is assumed or required by
   this design. Carry the rank1 local value/status in that reply as well;
   its incremental readback cost belongs to `u_return`.
3. Compare logit values, then choose the lower **global** index on equality.
   Keep the original BF16 output rounding before comparison, including
   signed-zero ties. OR both finite/error flags and retain sticky error
   handling; a nonfinite logit is not permission to emit a winning token.

Packet77's 96 `transfer.half_streams`, 96 `transfer.half_token`, 288
`transfer.readback`, and all sampled draft upload/proposal/status events have
zero-width timestamps. The valid draft hidden-copy events are **same-card**
copies, not inter-card transfers. Neither source can price the new DMA legs.
The multi-millisecond rank0-finish→rank1-start gap includes other dependencies
and is also not a memcpy cost. See the source hashes and event counts in JSON.

### (i) Target head: dependency chain on both paths

Let `F = 1.403683854 ms` be the full target head, `J = 0.022874302 ms` its
argmax, `x = k/248320`, and `a = A + spec_offset`. For either `B = Bh` or `Bm`,
define `L = B-F-J`. This conservatively puts all retained non-head work before
head readiness; it does not pretend to recover an intra-command timestamp.

```text
Q(B,k) = max(
    L + E + x*F + J,                  rank1 rows then local argmax
    max(a, L+E) + I + (1-x)*F + J     rank0 finishes speculation, imports,
                                     computes its rows, then local argmax
) + V                               result return and exact global merge

hit:  D -> Q(Bh,k) -> emission
      Ht = D + Q(Bh,k) + Gh

miss: [D || R -> C] -> existing corrected-state handoff -> Q(Bm,k)
      Mt = max(D,R+C) + Q(Bm,k) + Gm
```

Rank0's speculative half is already inside `Q`; it is not added a second time.
Both paths transfer **the final hidden vector of the current verified target
half from rank1**. Rank0 does not use its speculative half's hidden state as
the target head input. Its auxiliary head waits for speculation to finish,
uses separate scratch, and must not mutate the speculative image or KV.
No transfer/compute overlap or concurrent heads and target layers on rank0
is credited. Rank1's export is charged before its own head starts.

At the mean hit crossover, while `a > L+E`,
`1-x = (Bh-a+E-I-J)/(2F)`. The hit path dominates the optimum because hits
are more frequent; the miss-conditioned `Bm` is still used separately.
The full 0.544 ms slack cannot become a 0.544 ms saving: moving rows both
shortens rank1 and lengthens rank0, plus the extra reduction and handoffs.

Applying the chosen split to each actual first-99 interval predicts
**54.753214 tok/s (+1.1952%)**, using the median of prompt-class medians.
All 252 modeled misses improve, by at least **0.120468 ms**; a few low-slack
hits become up to **0.042568 ms slower**. These are conditional model effects,
not measured guarantees for future misses. The full per-prompt calculation
is retained; it is separate from the aggregate 54.689808 estimate above.

### (ii) Draft prefix: hits only

Let `P = 0.520766156 ms`, `Jd = 0.021087229 ms`, `y = k/91392`.

```text
Dhit = D-P-Jd + E + max(y*P+Jd, I+(1-y)*P+Jd) + V

hit:  rank1 draft trunk -> exact normalized draft vector -> E
      -> [rank1 prefix rows || I -> rank0 suffix rows]
      -> local argmaxes -> V -> publish the identical guess
      -> [Bh || A] -> emission
      Hd = Dhit + max(Bh,a) + Gh

miss: unchanged [D || R -> C] -> [Bm || A] -> emission
      Md = max(D,R+C) + max(Bm,a) + Gm
```

The hit/miss here is known **at interval entry**, from the guess just verified,
not from the new draft guess. On a hit, rank0 accepts its completed speculative
state while rank1 runs the draft trunk, then helps with the prefix head before
the next `A` begins. This uses the idle period **during D**, not an imaginary
overlap with the preceding target head. On a miss, issue no rank0 draft-head
work, transfer or wait: the complete old draft remains on rank1 and overlaps
`R+C`. Keep all 91,392 prefix rows resident on rank1 for that path.

The continuous balance is `y = (P+I)/(2P)`; the grid winner is `k=46080`.
Every modeled hit saves **0.232799 ms** and every modeled miss is unchanged.
Using the actual per-prompt hit counts gives **54.648868 tok/s (+1.0024%)**
class-balanced, separately from the aggregate 54.523528 estimate.
This does not reopen packet79/45's whole-draft relocation: the draft trunk,
state and miss work all remain on rank1, with identical prefix coverage.

## What failed or remains uncertain

The full-cost +0.5% condition cannot be established from zero-width DMA timers.
The following sensitivity **assumes**, rather than measures, equal additional
latency on each of the export, import and return legs. Each row reoptimizes `k`.
The comparison is the aggregate packet85 forecast against the measured control.

| Extra unknown ms per leg | Target k | Target tok/s / gain | Draft k | Draft tok/s / gain |
| --- | ---: | --- | ---: | --- |
| 0 (optimistic bound) | 201,728 | 54.689808 / +1.0780% | 46,080 | 54.523528 / +0.7707% |
| 0.025 | 201,728 | 54.540667 / +0.8024% | 48,384 | 54.378704 / +0.5030% |
| 0.050 | 201,728 | 54.392338 / +0.5282% | 50,688 | 54.232113 / +0.2321% |
| 0.075 | 201,728 | 54.244813 / +0.2556% | 52,736 | 54.089117 / −0.0322% |

At this rate definition the target allows **52.582 µs extra per leg**,
157.747 µs total, before falling below +0.5%. The draft allows only
**25.289 µs per leg**, 75.868 µs total. These are **budgets**, not evidence
that the transfers fit. If only return/merge adds cost, the corresponding
budgets are 105.165 µs (target) and 62.740 µs (draft). Allocation of latency
among legs matters; JSON also solves the export-only and import-only cases.

Other limits remain explicit:

- Linear row scaling at equal card bandwidth is an assumption. JSON includes
  rank0 head-time multipliers from 1 to 2, each with a new optimum. Keeping
  per-logit arithmetic does not prove a shorter row grid keeps its bandwidth.
- Exactness requires complete rows with unchanged reduction order, operands,
  Q6 expansion, scales and BF16 rounding. Global row addressing and local
  argmax offsets need real-shape byte checks. No CPU model proves device parity.
- At the nominal splits, rank0 needs **157,480,960 bytes** of target-head
  weights or **153,154,560 bytes** of draft-prefix weights (3,380-byte expanded
  row stride), plus logits, scratch and staging. These are allocation formulas,
  not memory admission. The target suffix is above the draft prefix and could
  leave rank1; a draft-only suffix must remain duplicated for rank1 misses.
  Existing arena budgets and reserves must stay unchanged.
- Packet85's mean model and a class-balanced rate are different aggregations.
  Both are reported. No guessed acceptance multiplier, new tokens, cache reuse,
  widened quality tolerance, or lower-precision KV enters the calculation.
- The split protocol would need progress while both ranks are pending, bounded
  sequence ownership, completion/error propagation, and correct EOS/cancellation
  handling. Adding a blocking mailbox wait can erase these small margins.

## Evidence and patches

- [DECISION.json](DECISION.json): full precision, source SHA-256 manifest,
  transfer-event counts, baseline correction, grid optima, per-prompt replay,
  transfer budgets, and slower-rank0 sensitivity.
- [model.py](model.py): standard-library CPU reproducer importing packet85's
  `intervals`, `components`, `paths`, `rate` and class-balanced aggregation.
- [Packet85 model and limitations](../packet85-critical-path/MODEL.md).
- Packet77 retained local evidence:
  `stage2/screen/v4-lanes/evidence/packet77-attribution-B-a/run/`, specifically
  `control/*/receipt.json`, `control/summary.json`, `summary.json`,
  `attribution-summary.json` and hashed `attribution/*/rank1/sites.jsonl`.
  These ignored raw receipts are not supplied by a clean Git clone; the JSON
  pins the required bytes. This is not a public reproducibility claim.
- [Controller](../packet77-attribution/native_controller.hpp),
  [target worker](../packet77-attribution/rank.hpp),
  [draft worker](../packet77-attribution/mtp.hpp),
  [prefix identity](../packet77-attribution/p56_config.hpp),
  [finite/tie reference](../packet77-attribution/core_v2.hpp), and
  [host attribution caveats](../packet76-rank1-host/ATTRIBUTION.md).
- [Packet79 negative placement result](../packet79-draft-rank0/DO-NOT-REPEAT.md)
  and [packet45 boundaries](../packet45-merged3/DO-NOT-REPEAT.md).
- [Task note](../../../../notes/2026-10-18-own-runtime-packet87.md).

No engine patch, GPU job, service, queue, sudo command, setting change or reboot
was used. Only this new packet directory and the explicitly requested new note
were written. `CURRENT.md` and every prior evidence tree remain unchanged.

Recompute/check from the repository root:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet87-slack-model/model.py </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet87-slack-model/model.py --check </dev/null
```

The inherited 4 GiB address-space cap remains. Checks require identical
packet85 components and shared source hashes, all 1,188 intervals, exact
unsplit recovery of the measured control rate, and no worse nominal modeled
misses for either split. They check accounting, not new runtime correctness.

## When to revisit

Reopen with a valid **host-clock, end-to-end** price for transferring a 5,120-byte
normalized vector rank1→host→rank0 and returning the local best value/index/error
to the controller, including ordered waits and progress. The useful next
measurement is that bounded transport operation, not a whole-draft relocation
or an engine rewrite. No device experiment is scheduled or authorized here.

Insert those costs into `E/I/V`, reoptimize `k`, and require at least +0.5%
against the matched control before preparing a seal-ready implementation design.
The target split has the larger budget; the hit-only draft split has the clearer
unchanged-miss path. Any later implementation still needs unchanged per-logit
bytes/ties/finite checks, memory admission, deterministic and fresh-process
oracle gates, and matched fresh-server speed evidence. No speed is promoted
by this packet.
