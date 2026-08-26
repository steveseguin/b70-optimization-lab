# Current-f01e AutoRound TP4/MTP0 PIECEWISE F16 depth R1

State: **preregistered, not launched**.

This packet measures the current official-f01e AutoRound TP4 target-only
PIECEWISE graph profile at exact active contexts 2K, 4K, 8K, 16K, 24K, and
32K. It uses one fresh server lifetime, one slot, F16 KV, capture size one,
and a fresh ext4 rank-scoped compile cache. Context zero remains missing; an
ordinary short prompt is not relabeled as an empty vLLM serving request.

The already qualified current-f01e TP4/MTP0/eager/F16 curve is the same-image,
same-topology target and quality oracle. Every graph output must exactly match
its eager 128-token output at the same depth. The graph quality battery must
pass all objective checks and `baseline_match_all` against the frozen eager
quality receipt. This is a graph-mode comparison, not a cross-model oracle.

The dated b2dd/1e90 TP4 FULL_AND_PIECEWISE curve is pinned only as historical
graph comparison evidence. Its runtime, graph mode, capture sizes, memory
setting, and cache identity differ. Its tokens are recorded for review, but a
cross-runtime mismatch is only a caveat and its speed is not a floor.

Startup must prove AutoRound `quantization=inc`, `enforce_eager=False`,
PIECEWISE mixed prefill/decode capture, graph completion, all four TP4 workers,
and the absence of FULL decode capture. The candidate must retain only
rank-scoped `rank_0_0`, `rank_1_0`, `rank_2_0`, and `rank_3_0` compile
artifacts. All six depth requests require exact length, 128 returned token IDs,
conventional 99-interval accounting, and cache zero. The full battery requires seven exact
cases, eight deterministic repeats with one hash, the long-context needle,
24 same-topology baseline comparisons, and cache zero on all 16 requests.

There is no speed floor. A slower valid profile is additive Grade C evidence;
it cannot replace the eager profile, the dated graph profile, a protected
short-workload route, a historical high, or a LocalMaxxing row. Partial,
quarantined, failed, or negative evidence is retained exactly and never
silently retried. Publication and descendant graph+MTP execution are both
explicitly disabled.

Static validation is inert:

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp4-mtp0-f16-piecewise-depth-r1.sh --check
```

The exact acknowledgement for a later authorized launch is recorded in the
preregistration. This preparation performs no GPU launch.
