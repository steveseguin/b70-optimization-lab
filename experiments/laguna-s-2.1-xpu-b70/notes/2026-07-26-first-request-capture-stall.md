# Laguna — a 10.478 s graph capture sits inside the scored window of prompt 0

Date: 2026-07-26 America/Toronto

Measured on the width-12 run that scored **100.524890** tok/s.

## The observation

Every prompt's inter-token gaps are 0.020–0.031 s. Prompt 0's **first** gap is
**10.478 s** — roughly 500x normal — and every later gap on that prompt is
normal. It is 10.48 s of a 14.32 s generation.

| row | prompt tokens | ttft s | first gap s | tok/s 1-100 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 90 | 10.105 | **10.478** | **8.62** |
| 1 | 132 | 6.930 | 0.030 | 206.97 |
| 5 | 89 | 4.460 | 0.021 | 74.87 |
| 10 | 229 | 11.852 | 0.022 | 242.28 |

TTFT is not the anomaly: row 10 has a longer TTFT with a longer prompt and
scores 242. Row 0's prompt length, 90 tokens, is unremarkable.

## The cause

The audited breakable graph is captured on the **first live eligible decode**,
not during startup:

```
Application startup complete
suite starts                        10:49:44
Captured audited ... num_tokens=12  10:49:55   <- inside prompt 0
Replayed  audited ... num_tokens=12  10:50:04
```

`num_tokens=12` is the speculative decode shape, which vLLM's startup capture
phase never produces, so the capture escapes it.

This is **deliberate**, not an oversight. The scope that authorizes it is
documented as "Authorize only the guarded first-live Laguna M=8 target capture",
and graph capturing is enabled only for that guarded moment. Capturing against a
synthetic batch was evidently judged unsafe for graph validity.

## Why it matters more than its duration suggests

The score is a median over 13 prompts, so it sits at sorted index 6. Prompt 0 is
the smallest value, which pushes every other value down one position:

| scenario | median |
| --- | ---: |
| as measured, row 0 = 8.62 | 100.524890 |
| row 0 = 100 | 100.524890 |
| row 0 = 110 | 110.00 |
| row 0 >= 119.47 | 119.47 |
| median of the other twelve | 109.996666 |

So the median is dragged by roughly **9.5%** by one prompt's one-time
initialization. An earlier note in this lane asserted this stall was worth
"exactly 0.000" because medians are robust to outliers. That is wrong: a median
is robust to an outlier's *magnitude*, not to its *rank*, and this outlier
occupies the bottom rank and shifts the index.

## REJECTED as a route

Moving the capture to startup is a cheat and is not being pursued. Cold start
includes first-request initialization -- that is what cold start measures. The
system would not be one token per second faster; the measurement would simply
stop counting a cost the benchmark exists to count. The suite would still be
"cold" by every other criterion, which is exactly what makes the rationalisation
tempting and is why it is written down here as rejected rather than left as an
open option.

The finding still matters as engineering: a 10.478 s capture on the first live
decode is worth fixing for real users. It is not worth anything on this
scoreboard, and a fix should be measured on its own terms rather than folded
into a record attempt.

## Original framing, retained



That removing it is automatically legitimate. Twelve prompts measure decode
throughput; one measures decode throughput plus engine initialization. Moving
that initialization to startup would make all thirteen measure the same thing,
which is arguably more representative. But it also moves work out of the scored
window, and the deferral is deliberate rather than accidental, so it is a
benchmark-integrity decision rather than an obvious bug fix. It is recorded here
for that decision, not acted on.

## Status

Best valid measurement remains **100.524890** tok/s at width 12, 13/13 bitwise
exact, 146/145 topology, against the approved record of 94.920039.
