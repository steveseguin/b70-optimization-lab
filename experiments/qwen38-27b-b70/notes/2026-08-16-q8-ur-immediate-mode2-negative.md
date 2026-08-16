# Qwen3.8 Q8 Unified Runtime immediate mode 2: negative

Date: 2026-08-16  
Disposition: closed; retain `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`

## Question

The accepted TP2 reproduction explicitly selects Unified Runtime Level Zero
immediate-command-list mode 1. Current Unified Runtime source defines the
three values as:

- `0`: ordinary command lists (`NotUsed`);
- `1`: one immediate command list per queue (`PerQueue`);
- `2`: one immediate command list per thread and queue
  (`PerThreadPerQueue`).

Mode 2 is a genuinely different scheduling policy from the previously closed
mode-0 comparison. It could theoretically reduce host-thread contention, so it
received a matched direct decode screen.

## Result

Both arms used the accepted Qwen3.8-27B Q8_0 TP2 binary, model, tensor split,
F16 KV, and `p64/n256/r3` shape. The only changed variable was
`UR_L0_USE_IMMEDIATE_COMMANDLISTS`.

| Arm | Mean | Standard deviation | Samples |
| --- | ---: | ---: | --- |
| accepted mode 1 | `36.887491 tok/s` | `0.014290` | `36.8855`, `36.9027`, `36.8743` |
| candidate mode 2 | `36.000691 tok/s` | `0.061722` | `35.9938`, `35.9427`, `36.0656` |

Mode 2 regressed decode by **`2.404%`**. The difference is about twelve times
the combined sample standard deviations, so an endpoint-quality run would not
change the decision.

## Source and decision

The semantics were verified at Unified Runtime current commit
`d836f5ccb61b73092d90941a9d6d362887e33c5b`, in
`source/adapters/level_zero/common/device.cpp`. The same source also shows
that batching event completions applies only to non-in-order queues; it is not
a separate candidate for llama.cpp's in-order queues.

Keep mode 1 in the public reproduction. Do not retry mode 2 on this adapter,
model, and execution shape unless the queue topology or Unified Runtime
implementation materially changes.

Structured measurements and raw-file hashes are in
[`2026-08-16-q8-ur-immediate-mode2-negative.json`](../data/2026-08-16-q8-ur-immediate-mode2-negative.json).
