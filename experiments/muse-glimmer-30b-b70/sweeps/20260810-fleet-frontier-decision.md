# 2026-08-10 Fleet Frontier: Measured Shapes And Recommendation

Completes the big-win topology hunt. All numbers: greedy, 256 predicted,
3-class prompt set (prose/code/json), fresh server per config, upstream
`030ebb558` SYCL bmg-g31. Raw: laneA-F JSONL under
`/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/`.

## Measured frontier (per-replica avg of 3 classes; fleet = replicas x per-replica)

| Shape | per-replica avg | peak class | fleet | aggregate | quality tier |
| --- | --- | --- | --- | --- | --- |
| **2-card Q8_K_XL + dflash n5 p0.1** | **38.0** | code 44.8 | 2 | 76.0 | Q8 near-lossless (best sub-BF16) |
| 2-card dynamic + dflash n4 | 28.8 | code 32.9 | 2 | 57.6 | 0.2% (Meta-measured) |
| **1-card dynamic + dflash n4 p0.1** | **27.3** | code 30.7 | 4 | **109.2** | 0.2% (Meta-measured) |
| 1-card dynamic no-spec | 24.2 | flat | 4 | 96.7 | 0.2% |
| 1-card 17gb no-spec | 27.6 | flat | 4 | 110.4 | 1.0% (below bar) |
| 1-card 17gb + dflash n4 | 26.8 | code 31.6 | 4 | 107.2 | 1.0% (below bar) |

## Why the dflash multiplier is quant-dependent (key kernel finding)

Acceptance rates are nearly identical across quants (n4 code: 65-66%
everywhere), yet the speed multiplier is 2.39x on Q8_K_XL and only
~1.13-1.17x on the k-quant mixes. Modeling step times: Q8's batch-5/6
verify costs ~1.1-1.4x a single decode step, while the kquant mixes pay
~2-3x. Upstream SYCL has efficient batched (mmq-class) paths for
q8-family weights but falls off for the mixed k-quant tensor types, so
speculative economics currently only compound on Q8. This makes
batched-verify kernels for k-quants the highest-value source-work item -
it would take the 4x single-card dynamic fleet from 109 to a projected
~180-220 aggregate.

Also banked: dynamic single-card no-spec repeats diverge on all three
classes (kernel-level nondeterminism confirmed again, unchanged verdict).

## Pareto shapes and recommendation

Two shapes survive:

1. **Quality/latency lane (recommended default production):**
   2 replicas x (2xB70, UD-Q8_K_XL + dflash n_max=5 p_min=0.1, single
   slot). 76 tok/s aggregate, 29.7-44.8 tok/s per request, best quality
   short of BF16. Matches the operator's quality-first directive.
2. **Throughput lane (alternate, workload-switchable):**
   4 replicas x (1xB70, kquant-dynamic + dflash n_max=4 p_min=0.1,
   single slot). 109 tok/s aggregate, 21-31 per request, 0.2% degradation.

Serving rules from screens: single slot per replica (multi-slot dflash
collapses); concurrency = replica count; frontdoor caps active
generations at replica count.

## Later-lane (deferred source work, ranked by unlock)

1. Batched-verify SYCL kernels for k-quant mixes (unlock: ~2x on the
   quad-dynamic fleet -> ~180-220 aggregate).
2. Cross-card drafter tensor mirroring (`output.weight` shared-tensor
   abort at ggml-backend.cpp:930): restores dflash overlap on single-card
   targets.
3. Kernel determinism for exact greedy replay (promotion/record gate).
4. BF16 drafter for prose acceptance.

## Addendum: BF16 Arm A results (laneG, same evening)

BF16 2-card no-spec: 9.847 tok/s flat, and **fully deterministic across
repeats on all three classes** - the quant kernels were the nondeterminism
source. BF16 is the exact-replay identity for gates and records, today,
with no source work.

DFlash multiplies 2.92x on BF16 (efficient native batched verify):
n5 p0.1 = 22.6/33.6/30.0 (avg 28.7); deep blocks stay viable
(n15 p0.2 tops json at 33.9). Byte-exactness vs no-spec: code and json
match at every depth and across repeats; prose is nondeterministic within
a small near-tie variant set (k-quant drafter kernels remain in the loop;
a BF16 drafter is the likely completion of full exactness, but it does
not fit the 2-card BF16 envelope without rebalancing).

Updated Pareto set:

| Shape | per-replica avg | fleet aggregate | quality |
| --- | --- | --- | --- |
| 2x (2-card Q8_K_XL + dflash n5) | 38.0 | 76 | Q8, nondeterministic |
| 2x (2-card BF16 + dflash n5) | 28.7 | 57 | LOSSLESS, exact code/json |
| 4x (1-card dynamic + dflash n4) | 27.3 | 109 | 0.2% Meta-measured |

The lossless lane now runs at 76% of the Q8 lane's speed - a defensible
default under the quality-first directive; the operator picks the fleet.
