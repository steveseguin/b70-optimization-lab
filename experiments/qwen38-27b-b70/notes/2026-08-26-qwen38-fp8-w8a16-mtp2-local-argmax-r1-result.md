# Qwen3.8 FP8 W8A16 MTP2-reuse local-argmax R1 result

The exact vocab-parallel local-argmax treatment is rejected. It preserved the
sequential output surface, but did not improve single-user decode and made
high-concurrency throughput materially worse.

## Frozen result

| measurement | local argmax | unmodified MTP2 reuse | change |
| --- | ---: | ---: | ---: |
| one user after TTFT | `82.823927` | `83.646518` | `-0.98%` |
| c64 aggregate | `673.064810` | `737.190110` | `-8.70%` |

The single-user row narrowly passed the preregistered 1% retention allowance,
but was not an improvement. The c64 row missed the `875 tok/s` primary gate by
23.08% and was 38.34% below the selected MTP1 c64 profile. Replication,
concurrent semantic canaries, c128, and collective sub-variants therefore did
not run.

Correctness and accounting remained clean:

- all seven sequential case hashes and the eight-run repeat hash matched the
  unmodified MTP2-reuse control exactly;
- every quality and timed request reported zero cached prompt tokens;
- c64 returned 8,192/8,192 token IDs, passed output isolation, and matched
  56/64 same-server sequential oracles under the documented batch-shape
  dependence;
- both TP workers logged that the O(2×TP) draft local-argmax path was active.

The measured conclusion is only that reducing the draft collective payload
did not improve this end-to-end XPU service. A plausible explanation is that
the additional local max/reduction and small-collective synchronization costs
dominate at TP2, but this screen did not isolate those components. Do not cite
that explanation as a measured mechanism result.

The default-off patch and launcher remain archived for reproduction, not use.
The selected MTP1 service and target-only MTP0 aggregate profile remain
unchanged. See the
[structured summary](../data/2026-08-26-qwen38-fp8-w8a16-mtp2-local-argmax-r1-summary.json)
and [raw evidence](../data/qwen38-fp8-w8a16-mtp2-local-argmax-20260826-r1/).
No value is interpolated or extrapolated.
