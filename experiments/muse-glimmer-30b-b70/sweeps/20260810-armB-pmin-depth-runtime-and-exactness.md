# 2026-08-10 Arm B: p_min/Depth/Runtime Ladders And The Exactness Finding

Same runtime/identity as the bring-up ladder sweep (upstream `030ebb558`
SYCL AOT bmg-g31, UD-Q8_K_XL, dflash-kquant, 2xB70 layer split, greedy,
`cache_prompt=false`, 256 predicted tokens, 3 prompt classes). Two lanes ran
concurrently: GPUs 0+1 (lane A) and GPUs 2+3 (lane B). Raw JSONL:
`/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/laneA-pmin.jsonl`,
`laneB-depth-runtime.jsonl`, plus `forensics-texts.json`.

## Speed results (gen tok/s, accept% per drafted token)

No-spec reference: 15.87-15.90 tok/s on both card pairs, all prompt classes.

| Config | prose | code | json | avg |
| --- | --- | --- | --- | --- |
| nmax5 pmin0.05 | 29.78 (34.6%) | 43.64 (60.7%) | 37.09 (47.5%) | 36.84 |
| **nmax5 pmin0.1** | 29.73 (34.4%) | **44.82 (61.9%)** | 39.39 (52.3%) | **37.98** |
| nmax5 pmin0.2 | 28.77 (35.0%) | 44.07 (61.2%) | 39.56 (55.0%) | 37.46 |
| nmax5 pmin0.4 | 29.58 (59.0%) | 41.89 (76.1%) | 38.79 (71.0%) | 36.75 |
| nmax5 pmin0.6 | 26.73 (78.7%) | 36.29 (86.4%) | 37.20 (88.8%) | 33.40 |
| nmax8 pmin0.3 | 9.73 | 11.99 | 9.32 | 10.34 |
| nmax12 pmin0.3 | 11.24 | 12.51 | 9.52 | 11.09 |
| nmax8 pmin0.6 | 17.72 | 16.43 | 20.56 | 18.24 |
| nmax12 pmin0.6 | 18.45 | 17.86 | 18.04 | 18.12 |
| nmax5 graph-off | 29.60 | 43.74 | 37.73 | 37.02 |
| nmax5 dnn-off | 29.85 | 44.75 | 39.39 | 38.00 |

Findings:

- Best screened config: `n_max=5, p_min=0.1` at `37.98` avg, i.e. `2.39x`
  the no-spec baseline averaged across classes; per class `1.87x` prose,
  `2.82x` code, `2.48x` json. Speedup is strongly prompt-class dependent.
- p_min in 0.05-0.2 is a plateau; aggressive gating (>=0.4) raises accept%
  but reduces drafted volume and net speed. Deep blocks (n_max 8-12) lose
  even with confidence gating; at p_min 0.3 they are BELOW no-spec.
- SYCL graph-off and dnn-off are speed-neutral here (within run noise).

## Exactness finding (blocks promotion; redefines gate work)

Chain of probes, all greedy temp 0, fresh server per run:

1. Every DFlash config differed from its lane's no-spec reference text on
   at least one prompt class (code matched most often - sharper argmax).
2. Two identical spec runs differ from each other (`spec1 != spec2`):
   the spec path is nondeterministic run-to-run.
3. Two identical NO-SPEC runs on the same card pair also differ:
   nondeterminism is in the upstream SYCL target forward itself, not the
   drafter/verify logic.
4. No-spec differs across card pairs on prose/code, matches on json.
5. Conservative runtime (`GGML_SYCL_DISABLE_OPT/GRAPH/DNN=1`) still
   nondeterministic. `-fa off` still nondeterministic.
6. Outputs bounce within a small recurring variant set (an fa-off hash
   reproduced an fa-on hash); divergence points are coherent near-tie
   alternates ("physical design:" vs "node structure,"), never corruption.

Interpretation: a small number of near-tie argmax positions flip under
nondeterministic reduction ordering somewhere in the 2-GPU SYCL path.
Quality is not degraded (both branches are valid greedy-class outputs),
but the lab's strict greedy-replay exactness standard is NOT met by
upstream master on this stack, no-spec included. The Gemma/Qwen pinned
builds achieved exact replay on B70, so this is fixable at source level.

Pending discriminator: single-card no-spec determinism probe using the
official kquant-17gb artifact (download in flight) - separates 2-GPU
split-induced nondeterminism from kernel-level nondeterminism.

## Consequences

- Production/record promotion stays blocked on an exactness identity:
  either restore deterministic greedy on this stack (preferred; lab
  precedent exists) or formally define the reference identity and gate on
  it. Do not promote DFlash configs on speed alone.
- DFlash speed levers are banked and real: `n_max=5, p_min=0.1` is the
  carrying config for future exact-verified serving.
- Keep the runtime tree clean-master; exactness work goes to
  `patches/muse-glimmer-30b-b70/` with source snapshots when it starts.
