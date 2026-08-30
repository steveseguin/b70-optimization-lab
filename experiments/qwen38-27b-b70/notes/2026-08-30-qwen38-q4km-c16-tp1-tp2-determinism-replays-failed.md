# Qwen3.8-27B Q4_K_M c16 TP1/TP2 determinism replays: failed

Both fresh-server topology replays failed their own frozen token-ID oracle gates:

| Topology | Exact sequences | Diagnostic aggregate rate | Cache/isolation/kernel gates |
| --- | ---: | ---: | --- |
| TP1 | **9/16** | 15.527079806977602 tok/s | pass |
| TP2 tensor 1,1 | **9/16** | 17.574564881479727 tok/s | pass |

Both used one admission cohort, identical model/prompt/seed/batch settings, 128 retained tokens per request, zero prompt-cache tokens, zero cross-base collisions, WDC disabled, empty kernel-error artifacts, and clean shutdowns.

The identical failure count is not treated as proof of an identical bug, but the TP1 failure is decisive: nondeterminism exists without any cross-GPU collective. The next screen disables all lab fusion/Q8/reorder feature doors on TP1. If that reference profile replays 16/16, the tuned feature groups will be bisected back in; if it fails, investigation moves below those doors into the shared/base SYCL path.
