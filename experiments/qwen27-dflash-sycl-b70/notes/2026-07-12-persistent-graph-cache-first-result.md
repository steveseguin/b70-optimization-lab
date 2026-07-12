# Persistent executable-graph cache: first result

## Change

The SYCL backend now has a guarded persistent executable-graph cache enabled
only when both of these are set:

```text
GGML_SYCL_ENABLE_GRAPH=1
GGML_SYCL_GRAPH_CACHE_SIZE=N
```

The cache defaults to zero, is bounded to 64 entries, compares complete graph
identity bytes rather than a hash alone, and directly submits an immutable
executable on an exact match. A full cache falls back to ordinary execution.

## Evidence

- Xe2 AOT Release build completed successfully.
- `MUL_MAT_Q4_0_REORDER(n=1..17)`: 17/17 passed on B70.
- Short graph diagnostic: two recorded identities followed by 14 direct
  replays (`cache_hit=14`, `cache_miss=2`, `updated=0`).
- 128-token, three-repetition steady-state A/B on GPU 1:
  - graph off: 25.511 tok/s average;
  - persistent graph cache: 25.287 tok/s average;
  - cache evidence: 381/384 direct replays, three recorded identities.
- Strict cold no-spec suite with cache: 25.848 tok/s median, all semantic gates
  passed, and all `cached_tokens` values were zero.
- Deterministic temperature-zero, seed-42, 64-token parity run produced the
  exact same output SHA256 with graph off and cache enabled. Graph-off decoded
  at 26.038 tok/s and cached replay at 25.498 tok/s in this one-prompt check.
- Simultaneous strict MTP3 A/B on GPUs 2 and 3 passed both gates. Graph off was
  47.757 tok/s median (46.571 mean); cache enabled was 48.344 tok/s median
  (47.195 mean). The roughly 1.2-1.3% uplift is too small relative to suite and
  cross-card variance to promote without repeated crossover evidence.

The strict result is stored at
`data/qwen36-27b-mtp-gguf-q4-b70-baselines/graph-cache8-no-spec-strict-20260712T155546Z.json`.

## Classification

Mechanically successful, throughput neutral. This fixes the previous
rerecord/update failure and proves stable direct replay, but it does not recover
the inferred 7 ms dispatch bucket. The 128-token A/B is a slight loss within
run variance, while the strict suite is approximately unchanged from the
25.783 tok/s graph-off reference.

Do not enable this by default. Exact graph-off/output parity is established;
use the result to redirect effort toward fusion and measured queue/kernel timing.
The evidence contradicts treating generic submission overhead as the dominant
remaining whole-model cost.
