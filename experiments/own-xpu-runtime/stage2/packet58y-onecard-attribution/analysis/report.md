# Packet58y measured diagnostic split

The class-balanced diagnostic rate is 22.8605 tok/s. This is not a record.
The first cold prompt remains included. Host spans are descriptive; the table below gives optimistic removal bounds, not promised gains.

| Lever | Mean bucket ms/token | Perfect-removal gain bound | Decision |
| --- | ---: | ---: | --- |
| Compute-tail wait, including zero-copy miss kernels | 20.7657 | 93.59% | needs_causal_test |
| Token lookup, preparation and input upload | 10.2815 | 31.71% | needs_causal_test |
| Host command submission | 8.0879 | 23.04% | needs_causal_test |
| Cache publication and fill submission at the safe boundary | 1.5838 | 3.80% | needs_causal_test |
| Overlapped CPU cache planning | 1.1532 | 2.88% | kill_below_3pct |
| Token/route readbacks and cache bookkeeping | 0.8887 | 2.03% | kill_below_3pct |

Not measured by this diagnostic; coordinator reviews independent capacity evidence.

Not independently ranked: zero-copy miss kernels share the compute queue. Counts and logical bytes are measured; their removable stall time is unknown.

Device-class times and isolated miss-stall time are unavailable. No implementation passes solely on these upper bounds. The full numeric split and file hashes are in report.json.
