# Qwen3.8 Q8_0/F16 TP1 service-quality r1 result

The exact preregistered one-B70 Q8_0/F16 service tuple is
**service-quality-qualified**. The server became healthy, all sixteen requests
completed, cleanup returned GPU 0 to its normal idle state, and no model process
or port listener remained.

## Frozen checks

| Gate | Result |
| --- | --- |
| Deterministic semantic canaries | 7/7 passed |
| Same-prompt repeat stability | 8/8, one normalized-output hash |
| Long-context needle | passed; 7,617 actual prompt tokens inside the frozen 8,192-token service context |
| Prompt-cache accounting | 0 cached tokens on every one of 16 responses |
| Baseline parity | not required; Q4_K_M is a different weight quantization |

The long-context response was exactly
`B70_QWEN38_NEEDLE_20260816`. The short canaries returned the required exact
answers (`OK`, `satin cobalt orbit`, `60`, valid answer/unit JSON, `Au`, `yes`,
and `14`). This establishes service-path semantic, repeat, long-context, and
cache-isolation evidence for this exact Q8_0 tuple. It does not measure model
accuracy broadly and does not turn the raw `llama-bench` generation rate into
an HTTP or realistic-prompt speed claim.

Evidence is preserved under
[`../data/qwen38-q8weights-f16-tp1-service-quality-20260825-r1/`](../data/qwen38-q8weights-f16-tp1-service-quality-20260825-r1/),
including the exact command, environment, input hashes, response payloads,
qualification, server log, slot snapshots, and before/after host and GPU state.
The machine-readable result is
[`qualification.json`](../data/qwen38-q8weights-f16-tp1-service-quality-20260825-r1/qualification.json).

