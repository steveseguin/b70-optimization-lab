# Qwen3.8 FP8 W8A16 adaptive MTP2/MTP1 R1 result

R1 is quarantined before its aggregate-performance gate. The batch-size-one
arm was valid, but the first transition to more than one active request exposed
an unsupported dynamic-width assumption in the pinned XPU GDN kernel and
terminated the engine. There is no R1 c64 performance result.

## Valid evidence before the failure

- The exact schedule was `[(1,1,2), (2,128,1)]`: MTP2 for one active request
  and MTP1 for two through 128 active requests.
- The seven sequential cases and all eight repeat hashes matched the static
  MTP2 control, with zero cached prompt tokens in all 15 observations.
- The first eligible single response measured `82.995339 tok/s` after TTFT
  (`79.322013 tok/s` wall) and passed the frozen `82.810053 tok/s` retention
  gate.

The first excluded c64 transition produced no complete response and is a
failed shape transition, not a throughput measurement. R1 therefore never
reached its separately declared c64 screen.

## Bounded diagnostic replay

One diagnostic-only replay retained the failed container so its root trace
could be captured. It was not eligible for performance or promotion. A c2
request reproduced the same immediate failure, proving that the trigger is the
dynamic MTP2-to-MTP1 width change rather than c64 capacity.

Both TP workers reported the same assertion from `gdn_attention`:

```text
Expected spec_token == num_spec_decodes *
    (num_speculative_tokens + 1) to be true, but got false.
```

The scheduler keeps `spec_state_indices_tensor` at the configured maximum
three-column state width while passing a compact two-token-per-sequence buffer
for the active MTP1 step. The kernel incorrectly derived its loop width from
the padded state tensor. The follow-on scheduler `KeyError` is secondary to
the worker failure. Neither B70 reset or faulted.

The focused repair is archived as
[`vllm-xpu-kernels-qwen38-dynamic-mtp-active-width-20260826.patch`](../patches/vllm-xpu-kernels-qwen38-dynamic-mtp-active-width-20260826.patch).
It derives the active loop width from the compact token buffers while retaining
the original padded state-row stride. A separately preregistered R2 must first
pass the new padded-width kernel test and a c2 crash canary before any quality
or performance measurement is accepted.

See the [R1 preregistration](2026-08-26-qwen38-fp8-w8a16-mtp2-dynamic-mtp1-r1-prereg.md)
and [raw receipts](../data/qwen38-fp8-w8a16-mtp2-dynamic-mtp1-20260826-r1/).
No value is interpolated or extrapolated.
