# Qwen3.8 FP8 W8A16 adaptive MTP2/MTP0 R1 result

The built-in batch-size-dependent speculative schedule is closed negative. It
preserved the static-MTP2 singleton behavior, but it did not combine that
behavior with the target-only aggregate throughput in one service.

## Frozen result

| measurement | dynamic policy | corresponding static control | change |
| --- | ---: | ---: | ---: |
| one user after TTFT | `83.336453` | MTP2 `83.646518` | `-0.37%` |
| c64 aggregate | `641.328344` | MTP2 `737.190110` | `-13.00%` |
| c64 aggregate | `641.328344` | MTP1 `1,091.642460` | `-41.25%` |
| c64 aggregate | `641.328344` | MTP0 `833.695517` | `-23.07%` |

The exact runtime policy was `[(1,1,2), (2,128,0)]`: a scheduler step with one
active request used two draft tokens, while a step with two through 128 active
requests used target-only decoding. The first declared single-user response
passed the frozen `82.810053 tok/s` retention gate. The first complete c64
batch was excluded as transition/conditioning evidence and measured
`574.208668 tok/s`. The second, separately declared c64 batch measured
`641.328344 tok/s`, 26.71% below the `875 tok/s` gate.

Correctness and accounting remained clean:

- all seven sequential case hashes and the eight-run repeat hashes matched the
  static-MTP2 control exactly;
- every quality and timed request reported zero cached prompt tokens;
- both c64 batches returned 8,192/8,192 token IDs, had zero cross-prompt oracle
  collisions, and passed complete token-ID accounting;
- the declared c64 batch matched 55/64 same-server sequential oracles under the
  documented batch-shape dependence.

The measured conclusion is limited to this end-to-end policy and frozen
service shape. The screen does not isolate the costs of keeping the drafter
resident, scheduler transitions, graph shapes, or individual kernels; those
remain possible explanations, not measured causes. Replication, a 512-request
semantic canary, threshold sweeps, c128, and context ladders did not run under
the preregistered stop rule.

The launcher remains archived for reproduction, not promotion. Static MTP1 is
still the selected aggregate service, static MTP2 remains a single-user
research profile, and target-only MTP0 remains the no-speculation control. See
the [structured summary](../data/2026-08-26-qwen38-fp8-w8a16-mtp2-dynamic-r1-summary.json),
[raw evidence](../data/qwen38-fp8-w8a16-mtp2-dynamic-20260826-r1/), and
[preregistration](2026-08-26-qwen38-fp8-w8a16-mtp2-dynamic-r1-prereg.md).
No value is interpolated or extrapolated.
