# Why the depth curve flattens at 2, and what depth 4-6 should do (2026-09-09)

Qwen3.5-9B W4A16, TP1, one B70 on `steve-b70s`. Mean acceptance length read from each arm's own
server metrics (`SpecDecoding metrics: Mean acceptance length`), averaged over the last windows of
the strict suite; step cost derived as `acceptance / rate`.

| depth | accept len | of theoretical max | tok/s | step ms | d(accept) | d(step ms) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 1.000 | 100.0% | 64.157 | 15.59 | - | - |
| 1 | 1.809 | 90.5% | 93.092 | 19.43 | +0.809 | +3.85 |
| 2 | 2.377 | 79.2% | 110.088 | 21.59 | +0.568 | +2.16 |
| 3 | 2.764 | 69.1% | 110.675 | 24.97 | +0.387 | +3.38 |

The mechanism is a race between two nearly linear quantities, and it is already lost by depth 3:

- **Accepted tokens per step grow sub-linearly** and are decaying at a steady ~0.70 ratio
  (+0.809, +0.568, +0.387). Each extra draft token is accepted less often than the one before it,
  because it is conditioned on all the previous drafts being right.
- **Step cost grows roughly linearly**, about +3.1 ms per depth: one more draft pass and one more
  verify row.

Depth 2 to 3 is the crossing point: acceptance +16.3% against step cost +15.6%, net **+0.5%** -
which is exactly the measured +0.53%. The curve is not flattening by coincidence; it is where the
two slopes meet.

## Prediction for the queued depth arms

Extrapolating the measured decay and the measured step-cost slope:

| depth | projected accept | projected step ms | projected tok/s |
| ---: | ---: | ---: | ---: |
| 4 | 3.035 | 28.07 | **108.1** |
| 5 | 3.225 | 31.17 | **103.4** |
| 6 | 3.357 | 34.27 | **98.0** |

So depth 4 should be about **2.3% slower** than depth 3, and every deeper draft worse. `a4d4`,
`a4d5` and `a4d6` are queued and will test this directly. If they land near these figures the model
holds and the depth ladder is closed by understanding rather than by sweeping; if they do not, the
step-cost slope or the acceptance decay is wrong and that is worth knowing on its own.

This also predicts that **no depth knob will beat ~110 tok/s on this host**. Raising single-stream
throughput further needs a cheaper step, not a longer draft - which points the remaining ladder at
the draft-head and linear-path knobs (`FP16_LINEAR_ROWCHUNK`, `LM_HEAD_CHUNK_ROWS`,
`DRAFT_LM_HEAD_INT4_*`) and at the inductor autotune that this lane currently disables.

## Caveat

Acceptance length is averaged over the metric windows the server happened to emit during the strict
suite, not over exactly the measured tokens, so the step-cost figures carry that imprecision. The
comparison across depths is like-for-like because every arm was measured the same way, but the
absolute step-ms values should not be quoted as kernel timings.
