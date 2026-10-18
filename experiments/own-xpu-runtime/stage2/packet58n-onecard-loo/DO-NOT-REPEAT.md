# Packet58n decisions and boundaries

| Interpretation / arm | Outcome | Revisit condition |
| --- | --- | --- |
| Blame packet58k's bundle loss on more misses or scattered host-down reads | Unsupported: all 2,386 cache-count rows match; host-down K1 improves twice; host preparation gains 7.83 ms with major faults. [Analysis](ANALYSIS.md). | Matched isolated evidence showing a specific kernel or host-state cause. |
| Device-only tile16 with row-major host weights | Deferred: current pointer ABI has no layout tag; conversion/lifetime costs need proof, while retained host tile16 cases improve. | Sparse-miss evidence that host tile16 loses, plus a bounded conversion/dispatch design and exact gates. |
| Production / down-tile16 only / production | CPU-ready, no device outcome. | Coordinator's fresh whole-host gap and admission; complete all three arms once. |

- Do not silently change the control's route-exp32-rank4 or rows4-shared choices.
- Do not subtract lookup faults from speed, warm prompts/pages, drop caches,
  discard slow tokens or retry for favorable host state.
- Do not call zeros in disabled device profiling measured zero cost; ordinary
  per-layer hits and all per-layer durations remain unavailable.
- Do not bypass fresh K1 selection, newest-line-minus-two-seconds overlap,
  full host timing admission, every-token oracle checks or own-owner drain.
- One candidate load is a screen, not a speed verdict, deterministic repeat,
  strict final gate or submission. No record job is auto-launched.
- Packet58h's MTP closure and 58g/58i/58j cache/pointer/lifetime cautions stand.
- Existing packet and ops trees remain frozen. Retain the failed bundle,
  incomplete bracket and cancelled production-after as historical evidence.

[CPU preparation closeout](CPU-PREPARATION-CLOSEOUT.md).
