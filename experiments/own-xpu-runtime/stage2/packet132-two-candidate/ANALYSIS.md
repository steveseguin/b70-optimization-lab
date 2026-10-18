# Packet132: confidence-gated second candidate

**Closed: the +3% gate fails.** Across 120 positions from five independent
excerpts, the primary cost model chooses never: **0.00%** projected gain.
Every policy that actually enables a second candidate projects a slowdown;
the least costly is −0.20%. Even the incomplete expert-only sensitivity reaches
only **+2.25%**, or +1.77% on held-out text with its frozen training threshold.
No runtime candidate was implemented and no GPU ran in this study.

The [machine-readable result](result.json), [all 175 policies in four cost
scenarios](thresholds.csv), [full structured sweep](thresholds.json.gz),
[closeout](CLOSEOUT.md) and [DO-NOT-REPEAT row](DO-NOT-REPEAT.md) retain the decision.

## Question and scope

Could rank0 process two alternative tokens at the same position, only when
the draft is uncertain, and avoid enough corrected halves to gain at least
3% net? Each cycle still emits **one target-verified token**. This is sibling
speculation, not depth-two decoding, draft relocation or a two-token bonus.

The [plan](PLAN.md) freezes five 16-token midpoint excerpts from packet114's
original non-benchmark documents, with up to 24 generated target tokens per
excerpt. This is a small CPU study, not the ten 128-token inputs from packet129
or the twelve-prompt benchmark suite. No benchmark answers select thresholds.
Sources 1–3 train the policy; sources 4–5 provide a separate held-out check.
The user gate is the best primary projection on the independent corpus.

The target is Unsloth UD-IQ3_XXS, the quantized compressed version of Qwen3.8
Flash-Next. Target labels come from `iq3-p49-split32-v1`, the packet49 CPU oracle. Every
shifted draft context row is populated; `H[j]` and token `x[j+1]` predict
`x[j+2]`. The draft uses packet31's CPU INT8 semantic reference and IQ3
embedding/head, restricted to bundle7's 80,128-row head. **CPU draft/device
draft numerical parity is not established.** Packet129's small FP8-versus-INT8
acceptance difference does not establish that missing identity gate.

Confidence is either top-one minus top-two logit, or top-one probability
normalized over the admitted 80,128 rows. That probability is not normalized
over the full 248,320-token vocabulary. Strict `< tau` and stable token-ID tie
breaking are retained. Actual target tokens label outcomes only after draft
choices have been computed.

## Observed acceptance and threshold results

All five sources completed the fixed 24-token cap. The second choice equals
the target on **13 of 56 misses (23.21%)**. Always verifying both choices
would raise candidate membership from 64/120 (53.33%) to 77/120 (64.17%),
but that improvement does not pay for the extra work.

| Independent source | Positions | Top-one hits | Misses | Second-choice matches among misses |
| --- | ---: | ---: | ---: | ---: |
| Runtime objective | 24 | 8 | 16 | 2 (12.50%) |
| Host stability guide | 24 | 13 | 11 | 3 (27.27%) |
| Local operations | 24 | 12 | 12 | 3 (25.00%) |
| Recipe publication standard, held out | 24 | 18 | 6 | 2 (33.33%) |
| Storage headroom script, held out | 24 | 13 | 11 | 3 (27.27%) |
| Total | 120 | 64 | 56 | 13 (23.21%) |

Selected fixed-grid rows below illustrate the full sweep, with the primary
4.153946 ms extra-half cost and 15 ms saved per rescue. Rates are projections,
not measurements. “Rescues/misses” uses only flagged misses as its denominator.

| Strict confidence gate | Flagged cycles | Rescues/flagged misses | Resulting acceptance | Projected tok/s | Net change |
| --- | ---: | ---: | ---: | ---: | ---: |
| Never | 0/120 (0%) | 0/0 | 53.33% | 57.471 | 0.00% |
| Prefix probability < 0.100 | 1/120 (0.83%) | 0/1 (0%) | 53.33% | 57.357 | −0.20% |
| Margin < 0.500 | 20/120 (16.67%) | 5/17 (29.41%) | 57.50% | 57.250 | −0.39% |
| Margin < 1.000 | 35/120 (29.17%) | 8/26 (30.77%) | 60.00% | 56.781 | −1.20% |
| Margin < 1.125 | 38/120 (31.67%) | 9/27 (33.33%) | 60.83% | 56.849 | −1.08% |
| Margin < 2.000 | 58/120 (48.33%) | 10/39 (25.64%) | 61.67% | 55.073 | −4.17% |
| Prefix probability < 0.500 | 32/120 (26.67%) | 7/25 (28.00%) | 59.17% | 56.713 | −1.32% |
| Prefix probability < 0.925 | 75/120 (62.50%) | 13/48 (27.08%) | 64.17% | 54.433 | −5.29% |
| Always | 120/120 (100%) | 13/56 (23.21%) | 64.17% | 50.178 | −12.69% |

The raw miss rate is 46.67%, substantially different from bundle7's roughly
21%; these short excerpts cannot establish production acceptance. The 120
positions are correlated within five texts, not 120 independent trials.

| Cost scenario | Best pooled policy | Pooled projected tok/s | Pooled gain | Frozen training policy, held-out gain |
| --- | --- | ---: | ---: | ---: |
| Favorable primary | Never | 57.471 | 0.00% | 0.00% |
| Extreme expert-only | Margin < 1.125 | 58.763 | +2.25% | +1.77% |
| Favorable work, compute-only saving | Never | 57.471 | 0.00% | 0.00% |
| Duplicate target half plus state | Never | 57.471 | 0.00% | 0.00% |

The expert-only threshold rescues six misses on 25 flags in training and three
on 13 flags held out. Its training projection is +2.57%. Across all 115 finite
intervals its gain is +2.59%, still below the gate; the training-only finite
value is +3.10% and is retained as an endpoint-sensitive diagnostic, not a pass.
The primary's best finite-window gain remains zero. Standardizing to a 21%
miss mix leaves the primary best at zero and the expert-only best at +0.43%;
the fixed margin-1.125 expert-only policy gives −0.28% under that mix.

The most permissive +3% cost budget among the registered primary policies is
**1.952223 ms per flag**, at margin < 1.125, assuming the full 15 ms rescue
benefit and free policy/state handling. That is below even the 2.345046 ms
expert-only assumption. Keeping the primary's 1.808900 ms non-expert row work
would leave just 0.143323 ms for experts: about 94.0% of incremental expert
cost would need to disappear relative to M=1, before other overheads. This is
an algebraic revisit condition, not a measured sharing factor or proof of
impossibility. The compute-only rescue model permits at most 1.193570 ms.

## Measured inputs and the missing wall-time partition

The exact [packet128b table snapshot](inputs/BUDGET.md) has 66 hit and 18 miss
sampled cycles. Its instrumentation overhead gate **failed**: 51.475 tok/s,
0.888 of the 58.0 reference. Its class costs are diagnostic inputs to the
following projections, not qualified whole-engine timing or M=2 measurements.
The snapshot preserves the locally modified bytes without editing packet128b.
[Input identities](inputs/manifest.json) bind those bytes and the other notes.

| Rank0 cost | Diagnostic ms |
| --- | ---: |
| Expert gate/up plus down, one half | 2.39176 |
| Attention, GDN and QSA, one half | 4.94515 |
| HC/norm/merge, one half | 1.99551 |
| All target-half compute, excluding snapshot/head/idle | 11.36252 |
| Miss-minus-hit target redo compute | 11.35051 |
| Miss restore | 0.21359 |
| Miss-minus-hit observed compute idle | 2.00916 |
| Miss-minus-hit host command gap | 0.02564 |

Restore plus redo is 11.56410 ms of compute. The idle and host rows overlap
other work and cannot be added to make an exact miss wall-time saving. Rank1
waits 1.61955 ms for the suffix on hits and 1.46874 ms on misses; that is a
dependency on rank0, not idle rank0 capacity available for another candidate.

[Packet120](inputs/2026-10-18-own-runtime-packet120-grid-result.md) added
0.588 ms to hits by moving one layer onto rank0, while
[packet127](inputs/2026-10-18-own-runtime-packet127-grid-result.md) added
0.344 ms by moving another 35,840 head rows there. These incomplete brackets
are directional evidence of near-critical rank0 work. Accordingly every
extra sibling-half millisecond is charged as exposed in this model.
Packet120's control has a 25.768−14.922 = 10.846 ms miss/hit difference,
also smaller than the brief's 15 ms allowance. This is a separate diagnostic
comparison, not an exact restore/redo/wait partition.

## Incremental second-candidate cost

For independent uniform top-ten routes among 512 experts, the expected union
has 19.8046875 experts: the incremental expert fraction is `1 - 10/512`.
Actual sibling route overlap was not captured. Shared weights do not remove
the need for separate ordered accumulators, recurrence and attention state.

| Scenario | Extra rank0 ms/flag | Saved ms/rescue | Other allowances |
| --- | ---: | ---: | --- |
| Favorable primary | 4.153946 | 15.00000 | Free state selection and policy collection |
| Extreme expert-only | 2.345046 | 15.00000 | Every non-expert increment is free |
| Favorable work, compute-only saving | 4.153946 | 11.56410 | Free state selection and policy collection |
| Duplicate target half plus state | 11.984910 | 11.56410 | 0.02113 ms/cycle policy; 0.21359 ms/rescue state selection |

The primary repeats recurrence, route, expert activation/combine and QSA
attention/pool/select work. It grants all incremental dense, projection, HC
and other weighted sites for free. The 15 ms rescue saving comes from the
brief, and is deliberately favorable. The conservative scenario duplicates
target compute, charges one 0.52239 ms snapshot-equivalent plus 0.1 ms control
per flag, and uses the existing argmax scale as a top-two collection proxy.
These allowances are assumptions, not measured M=2 or top-two latencies.
The expert-only scenario is deliberately incomplete and is not a lower-bound
proof for an actual implementation.

Packet131 does **not** establish a free sibling-state bank. Its three-bank
scheme preserves committed A and old spare B while speculative work writes C;
a hit commits C/A and a miss restores A/B. A second sibling needs an independent
destination or a new lifetime proof. The 29,601,792-byte recurrent bank is
only part of the problem: residual snapshot state is 19,025,640 bytes, and
candidate KV, PLE, history, positions and ownership must also remain isolated.
See the [unchanged source note snapshot](inputs/2026-10-18-own-runtime-packet131.md.txt).
Even the primary scenario's free state management is an optimistic allowance.

## Projection accounting

Let `f` be the flagged fraction and `r` the rescued fraction of all positions:

```text
T = 17.4 + f * added_half_ms - r * saved_miss_ms
projected tok/s = 1000 / T
gain = 17.4 / T - 1
```

The anchor is the brief's rounded 17.4 ms, or 57.471264 tok/s, not a new
measurement. A 3% gain requires saving 0.506796 ms per token. The primary
requires more than 27.693% of flags to rescue a miss just to break even,
before any collection/state overhead. This screens a mechanism; it does not
predict a qualified class-balanced production record.

The detailed sweep also keeps finite intervals: interval i pays flag i+1
and receives rescue i, with no cross-prompt edge or wraparound. All-position
counts include the endpoints. A separate diagnostic standardizes hit/miss
strata to the brief's 79%/21% mix; it cannot establish that CPU confidence
statistics transfer to the production line. Original counts remain unchanged.
Each threshold also records the maximum incremental half cost affordable at
+3%; that is an algebraic cost budget, not a new timing measurement.

## Prior closures and validation

The initial negative-result review covered packet79 rank0 draft placement,
packet71c depth two, packet106 draft splitting and packet96 top-two siblings.
Packet96's older CPU sample and cost model chose never. This study uses fresh
independent text and newer diagnostic class costs; it does not recycle those
old confidence rows or reopen the earlier runtime designs.

The analyzer checks independent-source hashes, complete target termination,
target-label equality, draft prefix, unique positions, shifted input alignment
and prompt boundaries. Tests cover strict thresholds, no two-token multiplier,
delayed cost versus current rescue, and rejection of incomplete captures.
Neither CPU source checks nor a positive projection establishes device quality.

All eight analysis tests pass. The final analysis regenerates byte-for-byte,
and retained evidence passes the byte/hash checks: 81 copied files and six
archives, with no originals removed. The capture took 48 minutes 11 seconds;
all 13 child stages exited zero. Peak sampled supervisor-plus-child memory was
1,159,667,712 bytes (1.16 GB), below 8 GB. The supervisor exited normally.
There were no faults, retries, GPU jobs, services, sudo calls or setting changes
from this study. See the [capture completion](evidence/capture/completion.json)
and [retention manifest](evidence/capture/retention-manifest.json).
The five full cleanup receipts exceed 1 MiB each; their value, consumers and
restoration are documented in the [retention review](RETENTION.md).

The [source audit](evidence/source-audit.json) checks the CPU oracle's frozen
arithmetic, imported draft sources and native dependency hashes. The private
oracle changes only its address-space cap, context capacity (4096 to 128,
with at most 39 consumed positions) and diagnostic dump volume. A source audit
is not a fresh cross-capacity numerical comparison. No production runtime
source was changed. [Environment and admission](evidence/environment.json)
record the compiler, CPU library versions, model admission identities, affinity,
nice level and resource limits.

The [training selection](evidence/training-selection.json) was frozen and
committed before inspecting held-out confidence rows. The final analyzer
requires identical training hashes, counts, policies and projections. During
harness inspection an old packet49c input metadata file was displayed,
including encoded token IDs; those IDs were not decoded, scored or used to
choose this study's corpus, thresholds or costs. Every analyzed confidence row
comes from the new independent captures.

## Reproduce the analysis

From this packet directory, with the repository's pinned CPU dependencies
available:

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B test_analysis.py </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B analyze.py --check </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B audit_capture.py --check </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B retain_capture.py --check </dev/null
```

Analysis uses the retained rows and receipts. Retention checks also need the
private `build/capture` tree: restore its tracked JSON/log files and the archives
according to the retention manifest, or keep the original capture tree as done
here. The source audit additionally checks the original local oracle and draft
binaries, whose build commands and hashes are retained; binaries are not archived.
Archives preserve every target-state byte; every
member is compared and hashed before retention. No original is deleted and no
model weights are committed. A fresh capture needs the admitted external model
files and local CPU Python environment; those dependencies are not published
as a portable deployment recipe.

The full threshold grid is retained as CSV and deterministic compressed JSON,
with counts, confidence feature, threshold, projected rate, finite-window
accounting and the +3% cost budget. These are CPU acceptance observations and
cost projections, never measured device throughput or a production quality pass.
