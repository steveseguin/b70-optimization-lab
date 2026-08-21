# Qwen3.8 TP2 draft-INT4 margin qualification result

Date: 2026-08-20

Classification: **terminal bounded negative; no retry or full-25 arm**

Preregistration:
[`2026-08-20-draft-margin-tp2-qualification-prereg.md`](2026-08-20-draft-margin-tp2-qualification-prereg.md)

Structured summary:
[`2026-08-20-draft-margin-tp2-qualification-result.json`](../data/2026-08-20-draft-margin-tp2-qualification-result.json)

## Outcome

The TP2 engagement marker appeared exactly once on each worker, and the real
branch produced `598` strictly parsed, contiguous one-row records. The result
failed decisively:

- every record exceeded the required strict `max_abs_error < 0.125` bound;
- observed global error ranged from `0.96875` to `2.375`, with median
  `1.55078125`;
- the approximate gathered argmax differed from the gathered FP16 argmax on
  `23/598` calls;
- the `0.25` candidate repair corrected `16` of those calls, but the repaired
  argmax still differed from FP16 on `9/598` calls;
- on two calls the approximate winner had already matched FP16 and the repair
  changed it to a different winner; and
- the exact local FP16 winner was absent from a rank's candidate set in `38`
  rank records.

The source proof needs `margin > 2 * max_error`. For this observed sample that
would require a radius strictly greater than `4.75`, over nineteen times the
tested radius. This does not prove that every larger-margin algorithm is
incorrect, but it defeats the intended cheap bounded repair. No margin sweep,
retry, or full-25 performance arm is authorized.

## Arm status and integrity

The runner exited `13` because the immutable sealed checker rejected all `598`
numerical records and also observed zero determinism-pad markers instead of the
preregistered two. The latter is consistent with the three prompt prefills
having lengths `83`, `61`, and `849`, none inside the pad's strict
`128 < M < 512` band. Identity records that the pad was enabled, so this is a
workload-conditioned harness expectation mismatch, not evidence the pad was
off. It remains a formal arm-gate failure and is not relabeled away. The
independent numerical failure is already terminal.

The evidence underneath the failed gate is otherwise coherent:

- Q1 used TP2 on physical GPUs `2,3`, MTP5, margin `0.25`, the exact 4dd/339
  composite runtime, and commit `ea0924f5b`;
- the repair marker appeared exactly once on Worker_TP0 and Worker_TP1;
- all three prompts completed `128` generated tokens with `cached_tokens=0`;
- the benchmark freshness gate passed;
- exactly two outer and four AOT artifacts loaded directly;
- there were zero graph/AOT compile or save markers;
- pre/post cache manifests were byte-identical at `f3582440...`, tree
  `723c1599...`, `3,795` entries, `3,246` files, and `395,855,113` bytes; and
- supervision ended with an empty process group.

The interval speculative counters were `175/420` accepted/drafted
(`41.667%`). They are descriptive only. Qualification computed full FP16 draft
heads, performed three full-vocabulary gathers, copied evidence to CPU, and
wrote JSONL, so its displayed throughput is invalid and must not be compared
with the `101.170 tok/s` honest anchor.

## Frozen artifacts

Raw root:
`/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70/qwen38-detpad-composite4dd-mtp5-draft-margin025-tp2-qualification-q1-20260820`

- enclosing checksum manifest: `8d93682c6698be5b868024e4bd186c0a0e32c568962b4e2142f70f85b4fe111d`;
- qualification JSONL: `db316ff78d630f8942d0645db398e38772321c0ee2185097da49e910775cecc7`;
- sealed-gate JSON: `697641af34b7f6c290c6eb2a10e5faca8b680d130618c0843c5ca0da7b9089dc`;
- benchmark JSON: `f60f57940a12757c3c01f26b150ee3db06b590d2a18f889dbb31d64a69952cdf`;
- identity: `62b7de800b809bf8c71303acbf7dc906b85e7da5db658c4b629e6b3d53b971be`;
- server log: `1591814dcc217105728fb449ef0feac4054d5c1a9c1c6039b06c2227b3ba19d4`; and
- nested prompt-index-ordered token arrays, serialized as compact JSON:
  `bd0aa0d597dba44095e78844d48e92a367d49dad2dc0a020b43f6f55d629f299`.

## Decision

Close the `0.25` TP-safe margin candidate. Preserve the failed qualification,
do not retry or reinterpret it as performance evidence, and do not promote or
submit anything from Q1. The next optimization must use a distinct
source-backed surface. The leading current candidate is the packed MTP
target/verifier FlashAttention block; it needs its own bounded operator proof
before any server arm.
