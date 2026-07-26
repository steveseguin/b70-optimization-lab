# Laguna throughput-window accounting correction

Date: 2026-07-26 America/Toronto

Status: **the submitted `102.971435596` score is preserved as a historical
benchmark-convention result; the conventional inter-token rate is
`101.941721240 tok/s`.**

## Finding

The standalone-reproduction audit found an off-by-one convention in
`scripts/bench-openai-realistic-suite.py`. The historical field
`tok_s_1_100_after_ttft` used:

```text
100 / (timestamp[99] - timestamp[0])
```

The elapsed span from the first through the 100th timestamp contains 99
inter-token intervals. Conventional post-TTFT decode throughput for that same
window is therefore:

```text
99 / (timestamp[99] - timestamp[0])
```

Recomputing all 13 sealed rows from their recorded token timestamps gives:

| accounting | suite median |
| --- | ---: |
| submitted legacy inclusive-event convention | `102.97143559613157 tok/s` |
| conventional 99-interval convention | `101.94172124017027 tok/s` |

The conventional value is exactly 99% of the submitted value. It misses a
conventionally defined 102 tok/s threshold by `0.05827875982973 tok/s`.

## What changes

- Headline documentation must qualify `102.971435596` as the published legacy
  benchmark convention.
- New score-bearing runs must report the conventional interval field. The
  historical benchmark helper remains byte-identical for old pinned recipes;
  `scripts/qualify_realistic_window_metrics.py` now verifies its timestamp
  arithmetic and adds both explicitly named fields before promotion.
- The strict reproduction reports both values and does not call the
  conventional 102 tok/s objective complete.
- Any other historical result produced by this helper needs the same 0.99
  conversion before comparison with a conventionally counted rate.

## What does not change

- The raw timestamps, responses, and sealed artifact hashes are unchanged.
- The result remains 13/13 exact in both token IDs and output-text SHA-256,
  cache-zero on all rows, and valid under the recorded 146/145 graph topology.
- Relative improvements between rows scored with the same historical helper
  are unchanged because every affected value has the same factor.
- LocalMaxxing ID `cms2ccv2d00lps201rej94pjy` remains the approved receipt for
  the value actually submitted. It must not be deleted, silently rewritten, or
  duplicated. The tracked queue and receipt remain immutable evidence.

## Prevention

For every event-window metric, record both the event count and interval count
in the output schema. A test must use known timestamps and assert that `N`
events span `N-1` intervals. Result promotion must identify the exact formula,
not only a friendly metric name.
