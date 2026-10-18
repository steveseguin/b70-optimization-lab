# Packet 96: conditional dual-guess speculation — close

**Do not build or seal this design.** The fitted policy is to keep one guess.
It predicts **55.69 tok/s, +0.00%**, below the required **56.52535 tok/s
(+1.5%)**. Even the favorable sharing scenario selects no dual guesses on
the training prompts. A second state bank fits; it does not solve the cost.

These are CPU calculations, not measured speed or a quality qualification.
No GPU, runtime, service, queue or existing evidence file was changed.
[JSON](DECISION.json), [complete threshold sweep](thresholds.json),
[reproducer](model.py), [plan recorded before threshold results](PLAN.md),
[closeout](CLOSEOUT.md), [do-not-repeat entry](DO-NOT-REPEAT.md).

## Evidence and the important identity differences

The [packet31 acceptance file](../packet31-mtp-acceptance/acceptance.json)
contains **256 unique positions**, four prompts of 64, rather than the brief's
512. For `mtp_fp8_iq3`, there are 198 top-1 hits, 226 top-2 memberships and
245 top-4 memberships: **77.34375%, 88.28125%, 95.703125%**. Top-2 could rescue
28 of 58 misses (48.28%). Other draft variants and the repeated incident capture
are not extra independent positions.

Packet31 uses the CPU FP8 draft reference and the IQ3 target's
`iq3-p17-detmath-v2` arithmetic. Its README explicitly does not certify that
draft as bit-identical to the XPU draft. Packet84 uses `iq3-p49-split32-v1`,
the production prefix/head and an optimized draft. Consequently these acceptance
rates and confidence thresholds have **not** been validated on the record line.

Costs come from packet77's sampled classes and packet85's complete-command
model: packet70 wide64, draft-HC, batched rollback, 24/24, draft on rank 1.
Packet84 additionally has HC-wide, ordered host retirement and parallel
recurrence. Its record excludes route-fast; the packet84 full-shape census
entry used here matches the record's choices, not a mutable current selection.
The [submission ledger](../../../../results/localmaxxing-submissions.md) gives
55.686963 tok/s; this calculation uses the brief's rounded **55.69** anchor.
Neither packet31 nor packet77 is relabeled as packet84 measurement.

## What the draft's uncertainty tells us

The primary feature is the draft's logit margin `l1-l2`, flagged when it is
strictly less than theta. The fixed grid is 0–16 in steps of 0.125, then 32
and 64. The second feature is `q4 = exp(l1) / sum(exp(top4_logits))`, with
thresholds 0.25–1.01 in steps of 0.01. **q4 is not the full-vocabulary top-1
probability**: it is an upper bound and an uncertainty surrogate. The missing
tail logits prevent computing the real probability. Neither feature uses the
target token, target logits, future tokens or target route IDs at decision time.
Target tokens are used only afterward to label training outcomes and evaluate
the frozen policy on held-out data.

Selected margin rows below summarize all 256 positions. The JSON retains every
threshold for both features, with separate training/test counts and costs.
There are 210 policies including never/always. Threshold 0 flags none.

| Flag if margin < theta | Flagged positions | Fraction | Misses among flagged | Misses rescued by top-2 |
| ---: | ---: | ---: | ---: | ---: |
| 0.125 | 6 | 2.34% | 5 | 2 |
| 0.5 | 29 | 11.33% | 18 | 7 |
| 1 | 58 | 22.66% | 30 | 15 |
| 2 | 102 | 39.84% | 45 | 21 |
| 3 | 123 | 48.05% | 51 | 25 |
| 4 | 141 | 55.08% | 54 | 28 |
| 8 | 211 | 82.42% | 58 | 28 |
| Always | 256 | 100% | 58 | 28 |

For example, margin < 1 identifies many misses, but only 15/58 flagged
positions (25.86%) avoid a corrected half. The other 43 pay for a second guess
without a rescue. Catching all 28 recoverable misses requires flagging 141
positions at margin < 4.

### Held-out results

Fit on incident-retrospective and code-review (128 positions); then evaluate
once on customer-email and benchmark-analysis (128). Optimize training mean
cycle time, with ties favoring fewer flags. Both feature and threshold are
chosen on training data. The cost scenarios and grid were fixed in PLAN.md.

| Cost scenario | Training-selected policy | Training gain | Held-out gain | Held-out record-anchored tok/s |
| --- | --- | ---: | ---: | ---: |
| Favorable sharing | Never | 0.00% | 0.00% | 55.690 |
| Partial sharing | Never | 0.00% | 0.00% | 55.690 |
| Conservative | Never | 0.00% | 0.00% | 55.690 |
| Serial M1 fallback | Never | 0.00% | 0.00% | 55.690 |

Requiring a nonempty training flagged set selects **q4 < 0.28** for all four
cost scenarios: it flags one training miss, rescues none, and flags no held-out
positions. Under conservative costs it loses **0.775% in training** and
**0.218% held-out** (55.568 tok/s), since collecting the extra draft information
still costs time. This is a rejected active alternative, not the chosen policy.

Leave-one-prompt-out fits also choose never in every conservative fold.
Under favorable costs, three folds choose never; fitting without the incident
prompt chooses margin < 0.125, then loses **0.780%** on that held-out prompt.
The temporal check fits indices 0–31 of every prompt and tests 32–63: favorable
costs choose margin < 0.125 and lose **0.585%**; conservative costs choose never.
Even fitting and evaluating on all the data selects never in every cost scenario.
These small, correlated development samples cannot establish generalization.

## M=2 half cost: assumptions, bytes and state copies

The [packet77 class table](../../../../notes/2026-10-17-own-runtime-packet77.md)
is measured on layers 22/23, scaled by 18 GDN and six QSA occurrences per half.
It is an estimate of all 24 layers, not a measured whole-half partition.
The reproducer takes the unrounded per-site costs and distinct runtime weight
bytes from the paired attribution JSON. No attribution instrumentation runs.

For two independent uniform top-ten routes out of 512 experts:

```text
E[intersection] = 10*10/512 = 0.1953125 experts
E[union] = 20 - 0.1953125 = 19.8046875 experts
union/single-route = 1.98046875
```

The actual 24-layer tensor inventory gives **476,672,000 packed expert bytes**
per single top-ten route set and **944,034,000** expected union bytes.
Disjoint routes require **953,344,000** bytes. This counts each selected
expert's gate/up/down weights once, not physical DRAM transactions. The sampled
layers' corresponding runtime-weight estimate is 473,088,000 bytes; its
difference from the full inventory is retained, not fitted away.
Independence/uniformity is an assumption: sibling guesses may share more or
fewer routes. Packet31 has no target-route overlap data. A shared expert still
needs two distinct ordered activation/accumulator chains.

| Rank0 class group | M1 estimate, ms | Favorable added ms | Partial-sharing added ms | Conservative added ms |
| --- | ---: | ---: | ---: | ---: |
| Expert gate/up + down | 2.729367 | 2.676059 | 2.676059 | 2.729367 |
| GDN recurrence | 0.645012 | 0.645012 | 0.645012 | 0.645012 |
| Other work without shareable weights | 1.491870 | 1.491870 | 1.491870 | 1.491870 |
| Dense, projection, HC and other weighted sites | 6.983424 | 0 | 2.760293 | 6.983424 |

The third row covers route selection, expert activations/combine, shared
activation and QSA attention/pool/select. It assumes independent row work
doubles. The last row includes attention output, GDN projections/convolution/
gating, HC, QSA projections/preparation, router and shared down. In the favorable
scenario all these sites cost no more for two rows: deliberately generous,
including small weighted norms. In partial sharing their added cost is
`max(0, M1_site_ms - weight_bytes/(555e6))`. This credits one shared weight
read but repeats the residual work. It is an accounting scenario, **not** a
validated separation of compute, launch and bandwidth time. Conservative costs
repeat each site's whole sampled time: sharing bytes does not guarantee lower
latency when arithmetic, registers or launch work limit it. Thus it grants no
unmeasured timing benefit to dense/HC sharing. It still reserves only one copy
of the weights. No scenario predicts a measured memory bandwidth.

Recurrence has separate, same-position state for each candidate. Row 1 cannot
consume row 0's updated recurrence, convolution or appended KV. We double the
0.645012 ms work; we do not count the two candidates as sequential positions.

[Packet88's extraction of packet64/70 batched rollback](../packet88-miss-path/MISS.md)
retains **48,627,432 capture bytes** and **19,025,640 restore bytes** per operation.
The 29,601,792-byte difference is the already-omitted spare recurrence/conv
bank on a confirmed redo. These counts are payload bytes, not read-plus-write
traffic. A capture or restore has a descriptor upload and one flat copy kernel;
its standalone device latency was not recorded.

We charge **one additional full capture-equivalent write set per flagged
speculation** for the second branch's state. Its optimistic read-plus-write
cost is `2*48,627,432/(555e6) = 0.175234 ms`. The pessimistic whole-command
proxy is `R*48,627,432/19,025,640 = 1.455298 ms`, with R=0.569390 ms.
This scales host overhead as well as bytes; it is an explicit conservative
allowance, not a measured copy rate or a proven upper latency bound. No new
copy overlap is assumed. A real implementation must initialize and preserve
the correct extents; any additional capture/restore increases these costs.

On a rescued miss, switching to the complete second candidate state is priced
as 0 / R / 1.455298 ms for favorable / partial / conservative, serially exposed
after readiness. A pointer swap could be cheaper but needs an ownership proof.
Both-wrong misses keep the existing R+C path. Conservative costs add another
0.100 ms per flagged speculation for branch setup/discard/control.

Today's draft emits top-1 only. A new top-two (or top-four) reduction and
handoff is required on **every** position to evaluate the threshold. It costs
0 / 0.023 / 0.050 ms on the draft command in the three scenarios. The middle
number uses the existing approximate argmax scale only; none is a measured
top-two cost. It is usually hidden behind R+C on unrescued misses. Never-mode
leaves the existing draft unchanged and pays none of it.

| Scenario | Extra rank0 half, ms | Total M=2 half A2, ms |
| --- | ---: | ---: |
| Favorable | 4.988175 | 18.676452 |
| Partial sharing | 9.028532 | 22.716809 |
| Conservative | 13.404971 | 27.093248 |
| Serial M1 fallback | 15.143575 | 28.831852 |

M1 A=13.688277 ms already includes its ordinary capture and housekeeping.
Only incremental work is added. The serial fallback charges another complete
M1 A plus the extra copy allowance. None of these estimates includes a promise
that newly compiled M2 kernels avoid spills or retain the current throughput.
The favorable case is a favorable scenario under the stated independent-row
assumptions, not a mathematical lower bound on every possible implementation.

## Memory fit against packet84

At context capacity 4096, the **matching record-view** full-shape census has
rank0 arena use **27,685,394,516 bytes**, against a **32,212,254,720-byte** limit:
**4,526,860,204 bytes** of headroom. Its separate physical capacity/reserve
accounting leaves **6,510,402,792 bytes** free and requires at least 1.5 GB free.

One extra recurrence/conv bank is 29,601,792 bytes. The broader candidate
reservation duplicates **all** existing nonweight allocations, including both
recurrence banks, full KV capacity, workspace, snapshot and descriptors:

| Additional allocation category | Bytes |
| --- | ---: |
| Workspace | 285,836,076 |
| Recurrent state | 59,203,600 |
| KV | 58,195,968 |
| Runtime overhead, including private snapshot | 373,666,328 |
| Total | **776,901,972** |

That leaves **3,749,958,232 arena bytes** and **5,733,500,820 physical-free
budget bytes**. The existing allocation reserve remains intact. This
conservative reservation covers substantially more than one 48.6 MB capture;
capacity and per-step written extents are different quantities. Additional
M2 scratch would still need a census; no new allocation/startup test is claimed.
No extra rank0 head or draft relocation is needed. This is a 4096-capacity
check, not an assertion about arbitrary contexts or actual driver residency.

## Composition: current verification and next speculation

Packet85's exact unrounded components give **H=16.046348 ms** and
**M=27.700544 ms**; the brief's 15.8/27.1 approximations are not substituted.
The mean hit slack is 0.543719 ms; miss slack is 0.775532 ms.

Let `f[i]` be a flag computed from the draft for position i. At emission i the
unchanged target has verified the guess. `rescue[i]` is true only when f[i]
was set and the target token equals draft top-2. With extra draft cost d,
extra half cost a and rescued-state selection cost s:

```text
D' = D + d
A_next = A + f[i+1]*a
current top-1 hit: ready = D'
current rescued miss: ready = D' + s
current unrescued miss: ready = max(D', R+C)

H_i  = D'       + max(Bh, A_next+offset) + Gh
S_i  = D' + s   + max(Bh, A_next+offset) + Gh
M_i  = max(D', R+C) + max(Bm, A_next+offset) + Gm
```

The cost of a guess is paid in the preceding interval and its rescue saves
work in the following one. The model uses adjacent actual rows and keeps that
one-position offset. There are **252 intervals** overall and **126 per primary
train/test group**. No edge crosses a prompt or a temporal split, and no
wraparound is invented. As with packet85's finite emission window, the entering
speculation cost and departing correction benefit fall outside the window;
the all-position counts are reported separately. Rescues are assumed to take
Bh/Gh afterward; retaining Bm would make them slightly more expensive.

| Current result | Next speculation | Favorable ms | Conservative ms |
| --- | --- | ---: | ---: |
| Top-1 hit | Single | 16.046348 | 16.096348 |
| Top-1 hit | Dual | 20.490804 | 28.957600 |
| Rescued miss | Single | 16.046348 | 17.551646 |
| Rescued miss | Dual | 20.490804 | 30.412898 |
| Unrescued miss | Single | 27.700544 | 27.700544 |
| Unrescued miss | Dual | 31.913187 | 40.329983 |

Every interval emits **one verified token**. There is no `1+acceptance` or
two-token multiplier: these are alternative guesses at the same position.

For each policy, first compute its mean change versus the same packet31 rows
under packet85 costs, `delta_ms = candidate_mean - baseline_mean`. Then report
`1000 / (1000/55.69 + delta_ms)`. This additive transfer preserves the record
anchor without pretending the packet77 baseline already measured 55.69.
The JSON also reports raw model tok/s and the alternative multiplicative
transfer `55.69 * baseline_mean/candidate_mean`. Neither transfer qualifies
a class-balanced record from four old development prompts.

Always-on M=2 predicts **47.440 tok/s (−14.815%)** even with favorable costs,
and **33.668 tok/s (−39.545%)** with conservative costs, after additive transfer.
The fitted never policy remains **55.69** in both. Margin < 1, a useful
illustration of the intended uncertainty gate, loses **0.974% held-out** under
favorable costs and **8.604% held-out** under conservative costs.

The cost sensitivity refits on training only for each assumed half increment,
keeping conservative draft/selection allowances. At +1 ms it chooses margin
< 3.25 and predicts +4.72% held-out; at +2 ms it chooses < 1.5 and predicts
only +0.47%; at +3 ms it chooses q4 < 0.61 and loses 0.43%; at +4 ms and above
it chooses never. These are discrete scenarios, not interpolated measurements
or an invitation to choose a threshold from the held-out set.

## Arithmetic and state: today's guarantees

**Today's packet84 does not guarantee an M=2 half with identical per-row
outputs.** It is an M1 controller, and this branch-state design is unbuilt.
Changing a matrix operation's batch dimension alone gives no such guarantee.

There is useful prior work in
[packet68c's production-derived M2 operators](../packet68c-m2-from-production/README.md):
independent accumulators retain M1's K traversal, logical chains, split tree,
subgroup/workgroup geometry, BF16 boundaries and route-slot order. Its CPU
fixtures passed 1,428 byte checks under both compilers. Unsupported classes
use two serial M1 submissions; HC/router/shared tuples were not all fused M2.
Those source mechanisms show how selected operators can preserve per-row
arithmetic. They do not certify a new packet84 sibling-guess controller or
automatically port newer HC-wide/parallel-recurrence choices. No new kernel
or full-state gate ran here.

Any future implementation must branch from the same committed state; isolate
GDN/conv banks, candidate KV appends, PLE/token history, stream buffers, routes,
positions/extents and error/ownership metadata; and select the entire verified
candidate state. Both wrong requires a complete valid restore and corrected
M1 half. Nothing may sum experts in union order instead of each row's original
slot order, reassociate floating-point sums, change contraction/rounding, or
compress KV. Only the unchanged target's decision can select a candidate.
Exact operator, complete-state, token-oracle, repeat and fresh-process gates
would be required before any speed claim. Serial independent M1 execution
preserves the operator arithmetic most directly, but is the slowest cost case.

## Prior closures and disposition

The initial DO-NOT-REPEAT search covered packet71c depth two, packet79 draft
relocation and packet87 head/draft splits. This model keeps the draft on rank1,
keeps one verified token per interval and does not split either head. Packet71c's
roughly 47% endpoint loss warns against pricing whole M2 commands from device
kernel time alone; packet79 loses the draft/repair overlap; packet87 has
unmeasured transfer costs. None is reopened or used as a claimed new speedup.

Close **conditional top-two rank0 speculation at these costs and confidence
features**. Reopen only with matched production-draft evidence and a new
mechanism reducing the complete incremental half cost enough to pass a new
held-out +1.5% test, while preserving every per-row arithmetic/state gate.
More threshold fitting on these same 256 rows is not that mechanism.

## Reproduce and scope

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/stage2/packet96-dual-guess-model/model.py --check </dev/null
```

The command verifies source hashes through byte-identical recomputation,
packet31 unique counts, packet85 equations, no-flag baseline recovery, matching
record-view census, adjacency and the delayed-cost/rescue dependency. All new
files, including the [dated note](notes/2026-10-18-own-runtime-packet96.md),
stay in packet96 as required by the frozen-tree rule. No root note,
CURRENT.md, shared DO-NOT-REPEAT, live queue or prior packet was edited.
