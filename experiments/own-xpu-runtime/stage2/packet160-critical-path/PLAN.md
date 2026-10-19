# Packet160 — changing the two-card serial chain

**Decision: no candidate earns a ≥3% build brief from the available evidence.**
Head-only cooperation is too small. Earlier next-A alone does not advance the
next emission. Moving B work to rank0 consumes the capacity that A needs.
Splitting the entire draft has almost no allowance for its new communication.
The remaining larger possibilities need a new dependency or measured service
cost, not a renamed closed experiment. This closes this 50-minute CPU study,
not the two-card optimization lane.

No runtime, build, GPU, service, model/GGUF read, sudo, setting, live queue,
existing packet, screen or ops file changed. No performance result is promoted.
The record remains **58.798108759 tok/s**, bundle8/packet136, 24/24 layers,
rank1 MTP, fixed 80,128-row draft prefix, full BF16 KV/state and unchanged
`iq3-p49-split32-v1` verification. This is the quantized compressed Unsloth
UD-IQ3_XXS lane. Its recorded WS128 scope is retained; strict512 is false and
prefill is not measured for this identity.

## 1. Measured interval reconstruction

[Analyzer](analyze.py), [all 1,188 record intervals](evidence/record-intervals.csv),
[calculated results](evidence/report.json), [input hashes](evidence/input-pins.json).
The packet147 method is extracted as two pure functions from its pinned
packet126/p85 source; no runtime or parent CLI is imported/executed.
Every embedded request is hash-checked. All twelve requests are exact,
cache-zero device results. There are 932 hits and 256 misses.

An interval starts at verified emission p and ends at emission p+1. Hit/miss
describes the guess verified at the **starting** emission. The already completed
previous speculative A is not charged again. The following chain is cyclic:
the B that produced the starting emission precedes D; the next B is in the
same race as next-A.

```text
previous B -> verified emission p
               |                      |
       rank1 draft D           rank0 accept, or restore R -> correction C
               +---------- both ready -----------+
                          handoff
                     /                \
      rank1 B: body + target head       rank0 next-A
                 |                          |
           prefix ready                 suffix service
                 +------ full head merge ---+
                       verified emission p+1
```

`T = max(D, R+C) + max(B, A+offset) + G`.
G is a **signed accounting remainder**, not removable idle time. B includes
suffix dependencies, merge and reply; it is not GPU body time. Commands use
one host monotonic clock. Host/GPU or cross-device event clocks are never
subtracted. The per-interval CSV preserves every measured component, offset,
gap and winning branch.

| Measured host envelope, mean ms | Hit, 932 | Miss, 256 |
| --- | ---: | ---: |
| D | 1.597226 | 1.595828 |
| R | 0 | 0.551168 |
| C | 0 | 11.818807 |
| A | 12.482216 | 12.485768 |
| B, including target head/suffix | 13.086387 | 13.230429 |
| A start offset from B | −0.002108 | +0.000495 |
| First critical branch, max(D,R+C) | 1.597226 | 12.369976 |
| Second critical branch, max(B,A+offset) | 13.086387 | 13.230429 |
| G | 0.020811 | 0.013023 |
| Complete emission interval | **14.704424** | **25.613427** |

**B wins all 1,188 second races. D wins all 932 hit readiness races; R+C wins
all 256 miss readiness races.** Reconstructed intervals have zero numerical
residual at the stored precision. For each prompt calculate 99,000/sum(T),
take the median in each of six classes, then their median. This reproduces
58.798108759182306 exactly. Neither pooled mean time nor a median of component
times is substituted for that metric.

| Exact replay sensitivity for +3% on 58.798 | Net change needed |
| --- | ---: |
| D only, benefiting hits | **0.628451 ms/hit** |
| B only, A unchanged, allowing B to move independently | **0.495744 ms/interval** |
| C only | **2.337708 ms/miss** |
| A only with B fixed | Cannot reach 3%; even removing A saves zero |
| R only | Removing all R gives only +0.691% |

These are counterfactual sensitivity thresholds, not forecasts or new speeds.
Any proposed B reduction must also prove that its suffix dependency moves.

## 2. Tonight's scopes, without inventing a finer record trace

Packet136 did not record the later packet150/154 subscopes. It would be false
precision to paste their medians into each of the 1,188 record rows. We retain
two separate, source-bound layers of evidence:

* The record CSV above contains actual interval-specific D/R/C/A/B/offset/G.
* [scopes.py](scopes.py) joins **all 3,780 actual packet154 intervals** (five
  views × twelve requests × 63 intervals) to the real rank0/rank1 scopes.
  [Compressed CSV](evidence/scoped-intervals.csv.gz) retains their own measured
  D/R/C/A/B/G and exclusive host subsegments. [Report](evidence/scope-report.json)
  pins the original bytes retained in packet156, and verifies all tokens and
  draft proposals against the corresponding packet136 record prefixes.

Each rank's exclusive subsegments sum to its own observed interval. The
shortest enclosing host scope wins; asynchronous draft-pending residence is
only fallback. Ranks overlap, so **do not add the two ranks**. Missing a stream,
required scope, command join, exact output or clock format refuses analysis;
an absent overlap bucket within a fully validated interval is legitimately zero.
Prefill/terminal waits outside the measured window are not joined as decode
commands. This corrected the analyzer's initial overly broad join refusal.

| Independent diagnostic observation | Measured value | Use |
| --- | ---: | --- |
| p150 rank0 capture/accept/rollback | 0.743247 ms/cycle | Enclosing host cost, mostly off critical path; p153 tests its actual removal |
| p150 rank0 suffix head | 0.310820 ms/cycle | Real service, not idle rank0 capacity |
| p150 rank0 token preparation | 0.122935 ms/cycle | Not a new ≥3% pool |
| p150 merge/handoff waits | 1.852065 ms/cycle | Contains other rank's real work |
| p154 smoke total remote wait / overlapping draft | 1.546 / 1.227 ms/interval | Supplied smoke attribution, 756 intervals, not record measurements |
| p154 bracket controls remote reply wait | 1.5528 / 1.5853 / 1.5733 ms/cycle | Three controls; per-request medians |
| p154 bracket controls overlapping draft | 1.2438 / 1.2463 / 1.2406 ms/cycle | Same control summaries, separate from smoke |
| p154 draft issue | 1.571178 ms/cycle | Host issue overlaps kernel execution |
| p154 B issue / hidden export completion / B completion | 11.344964 / 8.872564 / 1.612015 ms/cycle | Nested scopes; never three additive segments |
| p154 explicit suffix wait, new per-interval replay | 0.001043 / 0.000940 / 0.001242 ms/interval | Control means, not a GPU idle measurement |
| p156 generously donated suffix window | +0.293 / +0.315 / +0.287% | Includes required pack/export, misses and boundary credit for free |

The record-to-scope correspondence is by prompt hash/ID and position, **not**
an assertion that different runs have the same timing. Source summaries for
p150/154 are preserved in report.json. The p156 enclosing-window result is a
more generous budget than its roughly one-microsecond explicit suffix wait.

Packet158's ROOFLINE is a third, historical identity: packet122 cyclic operator
replays, two processes, 40 post-warmup steps each, occupied context128. Per-step
group sums give input/embedding 0.184503, attention projections 0.232592,
attention 0.088526, routed experts 0.307689, shared expert 0.041962, final norm
0.054807, head 0.445348 and argmax 0.026355 ms: **1.381782 ms total**.
They do not measure tonight's per-interval GPU phases. The 1.571 host issue
time is not added to that total. The draft-kernel line remains closed.

## 3. Mechanisms and decisions

All numbers in this section are **modeled ceilings or explicit sensitivities**,
never candidate measurements. Percentage calculations reaggregate the actual
1,188 intervals. Build sizes are future planning estimates: S ≤500 changed
lines/≤150 MB artifacts; M 500–1,500/≤300 MB; L >1,500/≤500 MB. No build was
performed. Exact CPU/device proof and new memory admission would still be needed.

| Mechanism | Measured-input budget on 58.798 | Risk / size | Decision |
| --- | --- | --- | --- |
| (a1) Split only draft head rows across ranks | Half of 0.445348 ms saves at most 0.222674 ms/hit before transfer: **+1.043%** | Medium protocol/memory risk, M | Below 3%; p106b already lost |
| (a2) Split routed experts and head | Donate half of both complete groups: 0.376518 ms/hit, **+1.776%**, before transfers | High combine/state risk, L | Below 3%, even this generous design budget |
| (a3) Split every draft group perfectly in half | 0.690891 ms/hit, **+3.308%** with zero communication/serial fraction. Only **0.062440 ms** total new overhead allowed for 3%. One amortized p149 round trip leaves 0.610776 ms/hit, **+2.913%**; eight leave **+0.232%** | Very high arithmetic/transport/memory risk, L+ | No supported net ≥3% implementation; the ideal halving is not achievable evidence |
| (b1) Partial draft head emits provisional next-A token | Even free, perfectly correct earliest-head signal can hide no more than full head+argmax, 0.471703 ms/hit, **+2.235%**, *if* B follows it. With the unchanged B queue, A-only advance gives **0%** | High private-state/control risk, M/L | Below 3% even with donated exposure; do not build |
| (b2) Signal before draft trunk finishes | Removing all D while preserving acceptance is an impossible free ceiling: 1.253043 ms pooled saving, **+7.989%**. A real 0.8 ms lead needs about98.70% agreement even under donated exposure/full-drain correction pricing. No such signal or exposure is measured | Very high prediction/state risk, L | Research condition only; no supported build brief |
| (c) Expert parallelism inside B only | Perfect, exchange-free, equal-cost work balancing gives 0.317996 ms pooled saving, **+1.889%**. Rank0's next-A is running during B. A one-exchange/layer proxy costs 1.921–1.924 ms/half before peer compute | Very high scheduling/weight/combine risk, L+ | Below 3% in the supported busy-peer model; smaller messages alone do not reopen p149 |
| (d1) Whole draft or trunk moved to rank0, B started earlier | Same equal-cost two-card balancing problem; next-A and target suffix now share rank0 with draft. No measured shorter critical chain; p79 −2.3%/−1.3% | High state/memory risk, L | Closed relocation; not a new arm without a new measured schedule |
| (d2) Restore layered into correction / early loser witness | Donate every R: 0.118770 ms pooled, **+0.691%** | High rollback/lifetime risk, M | Below 3%, p121/144 remains closed |
| (d3) Extra verified lookahead / sibling / shared correction | C needs 2.337708 ms net/miss for 3%; p151 adds 17.96 ms/half wall, 9.21 ms device. p71c depth2 lost 46.8%; p149 transport alone costs 7.69 ms/miss | Very high, L+ | No relabeled depth2/sibling/shared-correction build |
| (d4) Prove target global argmax before reading all head rows | Could remove a target-head dependency, not just advance A. No measured valid bound/early-winner rate or current isolated full-head cost supports a numerical ≥3% ceiling for a concrete certificate | Very high numerical-proof risk, L+ | Specific next research question, not a ready build or measured gain |

### (a) Why p106b lost; what changed now

P106b retained the complete 91,392-row head on rank1 for misses, and on
confirmed hits split it into [0,46336) on rank1 and [46336,91392) on rank0.
It exported normalized hidden bytes, used a separate request/reply mailbox,
then merged exact row maxima before publishing the draft token. It was already
using rank0's draft-wait window: that idle interval is not a newly discovered
resource. Combined head+draft split had 15.677 ms hits versus 15.519/15.496 ms
controls; the target-head-only arm was 15.451 ms. The added draft split thus
cost about **0.226 ms/hit relative to head-only**. All were exact.

The data establish that the saved local head work failed to pay the new
export/rendezvous/peer service/merge path. They do **not** separately locate
the 0.226 ms regression in one transport phase. Do not call it measured PCIe
latency. Current bundle8 has an 80,128-row prefix, already split target head,
and newer body/snapshot choices. Its current historical head service allowance
is smaller, not evidence that the rendezvous got cheaper. No measured new
transport improvement reopens it. Full draft parallelism differs by splitting
trunk operations too, but has many serial producer/consumer boundaries.

Lossless construction would keep each output row's original arithmetic chain,
BF16 stores, exact nonfinite rejection and global lowest-index tie rule. Split
whole selected experts, return each expert's individual rounded output, and
perform the ten-term combine on its original owner in its original order.
Never sum rank-local expert partial sums. Draft state remains single-owned;
all publications follow real completion events and carry request/position/seq.
Deciding evidence: exact real-shape bytes, complete communication/queue event
times and a net D reduction ≥0.628451 ms/hit, including dispatch and merges.
The ~80 µs proxy is not a universal lower bound: a genuinely different measured
sub-62 µs **total** protocol would change a3's conclusion, but is absent today.

### (b) Early next-A needs both a correct signal and a useful recipient

With current scheduling, D still owns rank1's queue before B. Let L be a
provisional-token lead. Merely changing A's start gives
`max(D,R+C) + max(B,A+offset-L) + G`: the exact replay saves **zero**.
Advancing the suffix can help only where B waits for it. Tonight's actual
suffix waits are tiny; even p156's enclosing, free pack/export allowance is
below 0.32%. A partial head's 0.471703 ms donated upper allowance already
fails 3%, without charging its added publication or wrong guesses.

For a hypothetical **different B schedule** with full lead exposure, q is
agreement with the unchanged full draft, not target acceptance. Keeping the
original draft entirely intact permits identical proposal sequences: if the
provisional token disagrees, drain/discard its private A transaction, restore
all original state, and execute A on the original full-draft token. The target
still verifies every accepted token. No provisional token reaches output.
Target verification alone does not repair stale recurrent/KV/PLE/history state.

The conservative full-drain pricing used in report.json is
`net_hit_saving = q*L - (1-q)*12.369976 ms - added_protocol_ms`.
The recovery proxy is the **measured** record R+C on misses, not a measured
new provisional transaction. Under this pricing, zero added overhead and
full exposure, q for 3% must exceed `(0.628451+12.369976)/(L+12.369976)`:

| Assumed available lead L | Required agreement q for 3% | Explicit sensitivity examples |
| ---: | ---: | --- |
| 0.471703 ms, all head+argmax | Impossible | q=100%: +2.235%; q=97%: +0.402% |
| 0.8 ms | 98.70% | q=99%: +3.196%; q=97%: +1.912% |
| 1.0 ms | 97.22% | q=97%: +2.855% |
| 1.2 ms | 95.79% | q=97%: +3.815%; q=95%: +2.477% |

These are assumptions, **not accuracy estimates**. No fixed-suite token list,
history cache, learned draft or prompt reuse may supply q. A lower-cost graceful
partial-A cancellation would need its own measured stop boundary, saved work,
restore scope and next-A latency; it is not assumed to cost a full half, nor
assumed free. P151's +18 ms sibling is not used as this penalty: this is one
provisional A replacing the normal A, not an extra simultaneous sibling row.
Deciding evidence is a preregistered independent varied corpus, signal ready
time, agreement, full-draft preservation, actual B advance and correct/wrong
transaction cost. Existing receipts contain full-draft results, not early-head
rankings; this CPU task cannot infer that missing distribution.

### (c) Price the smaller expert exchange and the busy peer

P149's throughput-derived “~9 ms/miss” is a useful rough end-to-end warning.
Its direct, matched corrected-half means are more appropriate here:
11.804704 ms control mean; added **7.685006/7.697146 ms** in the two candidates.
All 331 corrections/view have exactly 96 round trips, 849,792 bytes sent and
1,362,048 returned. Original summary bytes are retained and re-hashed in
[this gzip](evidence/packet149-bracket-summary.json.gz).

Dividing by 96 yields **80.052–80.179 µs/round trip**, amortized over that exact
schedule. At 24 layers, one exchange each is a **1.921–1.924 ms proxy**; two
each, 3.843–3.849 ms. These are not new small-message measurements. Different
payloads, copy count, responders, queue contention and first-draft waiting can
change them. There is no fitted PCIe bandwidth/intercept from one payload mix.

An expert-only design can send one common BF16 hidden row (5,120 bytes),
ten selected IDs (40 bytes), and layer/position/seq/status to a peer holding
the required B-layer expert weights. Five complete remote experts return five
individual BF16 output rows (25,600 bytes plus status), allowing the original
ordered ten-expert combine. That is about **30,764 payload bytes/layer** before
extra headers, versus p149's average 23,040 bytes/exchange across its four
projection exchanges/layer. It reduces rendezvous count **four to one**; it is
not even uniformly smaller per rendezvous. Per-row tensor parallelism instead
requires gate/up and down synchronization, at least two phases per layer.

The draft-wait idle interval is earlier than B. During B, rank0 executes A and
then the target suffix. Offloading g ms of B at equal local/remote service cost
changes the race to `max(B-g+exchange, A+offset+g)`. With zero exchange and
perfect per-interval g selection, the optimum is `(B+A+offset)/2`, giving
**+1.889%**. This already donates arbitrary movable work and ignores the suffix
ordering restriction. Moving a large expert chunk makes A the bottleneck:
the illustrative g=1.9 ms case loses 6.94% even with free transport. Measured
rank1 MoE diagnostic time around 3.86 ms/half is not all parallelizable service;
the 1.9 ms case is an assumption, not a current isolated expert measurement.

Exactness requires original per-expert output bytes and original combine order,
unchanged routing/ties, BF16 KV, unique recurrent state ownership, versioned
buffers and explicit completion. Duplicate B weights on rank0 or remote reads
need a new admitted census; p149 did neither. Deciding evidence is a distinct
one-roundtrip expert-shaped service with rank0's actual concurrent A, net peer
busy time and full-memory admission. Free-peer correction results cannot price
this busy-peer schedule. A demonstrated remote marginal compute cost much below
local g could reopen it; simultaneous free execution is not supported today.

### (d) What would actually change the remaining dependency

An exact early global target winner would let verification finish before every
head row completed; an early **loser** only identifies a miss, not its corrected
token. The former needs a rigorous bound for every unread row under the actual
rounded arithmetic, complete nonfinite/error semantics, and tie handling. A
logit-margin heuristic or a partial head winner is insufficient. No such
certificate or its useful frequency exists in the inspected receipts. It is
an open algebra/metadata question, not permission to read weights or build in
this task. Another valid reopening would demonstrate a cheaper wrong-proposal
transaction plus a real B advance, rather than only earlier A.

For d4, the broad **B-only** donation ceiling is0.635991 ms pooled/interval,
+3.857%, even deleting all B while keeping A; this is not an isolated head
measurement or a realizable certificate budget. There is no certified early
winner with enough frequency to support0.495744 ms of net B saving. A mechanism
that also changes A's or D's dependency would need a different measured replay.

The remaining exactness contracts are specific. Relocation (d1) preserves the
same draft row arithmetic and single-owned cache, transporting completed hidden
bytes with no alias to the next B writer. Layered restore (d2) must restore every
original bank/extent/history byte before its first consumer, including terminal
and abandoned-redo cases; an early loser is never a corrected token. Lookahead
or sibling verification (d3) must compute each row with the original target
arithmetic and causal cache extent, then commit only the verified prefix and
restore the full abandoned suffix. Its deciding evidence is a whole-engine
reduction in correction/verification cost, not operator-only M2 support or
unchanged final tokens with untested internal state.

## 4. Closed-arm census and novelty

Before candidate work, [audit.py](audit.py) searched all **223 rg-visible
DO-NOT-REPEAT.md files** across the repository, including other lanes and
vendored copies. [Manifest](evidence/prior-audit.json) binds paths/bytes/hashes;
[411 matching lines](evidence/prior-matches.txt) preserve the search. Later
result notes override older preparation text that still says pending.
The final hash recheck caught a concurrent packet58ajc one-card readiness
amendment. It was read in full and [recorded separately](evidence/prior-audit-updates.json)
without rewriting the entry audit; it changes none of these two-card inputs or
decisions. All other entry negative-index hashes stayed unchanged.

| Required prior | Retained exclusion; distinction here |
| --- | --- |
| 66 / 71c | Depth2 is not reopened; completed engine −46.8%, extra-row traffic remains. New provisional-A discussion does not batch another verifier row. |
| 79 | Whole draft relocation lost −2.3%/−1.3%; a1 splits rows, a3 distributes operations, neither gets its old projected gain. |
| 106 / 106b | Hit-only draft split already consumed the idle-rank0 opportunity and lost. Current prefix shrank; no measured cheaper rendezvous. |
| 120 | Layer move −3.9%, incomplete trailing control disclosed. B-only expert placement differs in granularity, but still pays busy-rank0 cost. |
| 126 | Early stateful draft is not free reorder on one CCS; no second unresolved transaction without new ownership. Early A is a different branch, and fails to advance B here. |
| 132 | Independent second-candidate rescue model <3%; no training/tuning against the fixed suite. |
| 145 | Router/GDN-z order600 null; no locality or body-kernel campaign hidden inside this study. |
| 149 | Four-exchange shared correction is closed; one-exchange expert service is separately priced and unmeasured, not declared rescued by byte scaling. |
| 151 | +17.96 ms wall / +9.21 ms device sibling-half cost; no full-M2 build. Single provisional rollback is distinct but has no cost proof. |
| 153 | Static snapshot +0.35%, exact, below its bar; no recycling its enclosing 0.743 ms as exposed saving. |
| 156 | Host suffix slack <0.32%; earlier device-enqueued branch would need producer/event evidence, not this host timestamp. |

## 5. Admission and reproducibility

No mechanism above has a **supported net ≥3% ceiling for a concrete new
schedule**, so there is no `briefs/<candidate>.md`, no queue proposal and no
READY marker. Ideal whole-D removal, ideal free-B removal (+3.857%) and
perfect whole-draft halving are retained as sensitivities, not qualifying
mechanisms. Not issuing an unqualified build is the requested decision gate.

If new evidence qualifies one, its CPU build brief must require: analyzer
replay on the real retained parent and corruption tests **before** any device
request; in-run checks of presence/format/exactness at the first completed
request, followed by the complete suite; no elapsed-wall data-proof deadline
at any wrapper/client/native layer (coordinator freezing is allowed). Keep
fault/stop/storage/memory safety checks and graceful drain. Validate original
tokens, original full-draft proposals when claiming scheduling-only equivalence,
all state/extent/history ownership, wrong guesses, EOS/capacity, cancellation,
request reset, deterministic repeats and fresh processes. No precision change.

Prepare packet-local, unqueued `proposals/smoke-A.txt`, `bracket-A.txt`,
`smoke-B.txt`, `bracket-B.txt`; each lane's 12×64 exact smoke precedes its own
one-load C/X/C/X/C diagnostic bracket, with independent fresh-load qualification
after a win. A is cards0+1, B cards2+3, resolved through the topology authority;
no overlapping lane/one-card reservation. Test real entry/report/loader/native
limit paths and temporary queue plans. **READY is written last**, only after
final proofs, sealed paths, retention and both-lane admission. A CPU brief is
never a device quality/speed pass. No broad queue edits or autonomous launches.

Resource labels are explicit: **CPU preparation stops below 27 GB root free**;
**device floor is 25 GB plus planned writes**, not 27 GB. Current study uses
nice19, CPUs8–15/24–31, Python `-B`, closed stdin and a 2,000,000,000-byte address
space cap installed only in CPU mains. Peak observed replay RSS is below
150 MiB; no build outputs or device writes. Final validation records actual
retention and space. The initial pull refused unrelated dirty orchestration
files; fetch confirmed main==origin/main at ca9822f755899d9b0aec1b96ed8298fe1d8f4202.

From the repository root:

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet160-critical-path/analyze.py --check </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet160-critical-path/scopes.py --check </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet160-critical-path/test_analyze.py </dev/null
```

The first two read parent evidence only and compare packet160 outputs byte for
byte. No model file is opened. All 18 tests use real parent examples for
positive/numerical checks and deliberately corrupt copies for refusal checks.
Frozen packet156's retained raw streams are dependencies pinned by original
and gzip hashes, not copied or edited; packet136's embedded receipt archive is
also referenced by its immutable hash. The otherwise untracked packet149
summary is retained locally as a 5,551-byte gzip. The 1,297,878-byte scope CSV
exceeds1 MiB and has an explicit [retention review](RETENTION.md); it retains
all five views at their original floating-point precision, not rounded samples.
See [closeout](CLOSEOUT.md) and [work note](../../../../notes/2026-10-19-own-runtime-packet160.md).
