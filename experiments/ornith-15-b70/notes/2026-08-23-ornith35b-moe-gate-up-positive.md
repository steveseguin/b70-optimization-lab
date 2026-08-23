# Ornith 1.5 35B-A3B: routed-expert gate/up fusion

Date: 2026-08-23 EDT

Status: **accepted target-only package increment; +2.33% matched serving**

## Qwen-derived MoE boundary, retained on the tuned dispatcher

Each of Ornith's 40 MoE layers sends the same normalized FP32 activation and
eight selected expert ids through separate Q4_K gate and up `MUL_MAT_ID`
operations, then applies SWIGLU. Earlier fusion ideas were rejected because
they bypassed the tuned routed-expert dispatcher. This candidate instead
extends that exact reordered-Q4_K subgroup kernel: every subgroup computes the
same gate and up dot products in their original accumulation order, uses the
existing SWIGLU expression, and writes the original GLU destination.

The default-off matcher requires the exact Ornith tensor names, layer range,
Q4_K `[2048,512,256]` weight stacks, shared FP32 `[2048,1]` activation, shared
eight-entry I32 route ids, `[512,8]` outputs, adjacency, sole-use subgraph,
strides, layouts, and one-device buffers. Any mismatch falls back to the stock
three-node path.

The increment removes one duplicate input-quantization launch, one routed GEMV
launch, and the standalone GLU launch in each MoE layer: 120 launches/token.
The complete seven-optimization stack now removes 560 launches/token.

## Performance

One B70, local SHA-verified GGUF, F16 KV, flash attention, target only. All
measurements used final candidate library SHA-256
`cbe101e6573100e10877ee059f326b23580cc7c15161a132608c771d34840671`.

| Protocol | Controls | Candidates | Mean delta |
| --- | --- | --- | ---: |
| `llama-bench p0/n128/d0/r7`, mirrored | `118.673822`, `116.966600`, `118.535025`, `118.740883` | `120.609682`, `120.852637`, `120.724780`, `120.591165` | **+2.09%** |
| fresh 12-prompt server suite | `113.453206`, `112.632509` | `115.232218`, `116.128380` | **+2.33%** |

The fresh-server candidate mean is `115.680299 tok/s`; both candidates beat
both controls. Every process used 12 unique prompts once, prompt caching and
history acceleration were disabled, all rows reported `cached_tokens=0`, and
the required tokens 1-100 window and final gate passed. One candidate response
ended naturally after 507 streamed chunks and one control after 504; both are
well beyond the measured window and are retained rather than rerun.

## Correctness

- Same-final-binary forced 128-token output was byte-identical; both canonical
  transcripts hashed to
  `d25039a7a21fccc7eaf5f9414803f80c1e3b58cc900ad8034448df8edb57e38c`.
- The exact candidate fired 5,080 times, or 40 layers across 127 decoded graph
  evaluations.
- Engine and serving candidates showed the expected hit counts.
- The candidate passed 8x repeat stability, arithmetic, exact-copy, and JSON
  schema canaries.
- The complete patch applies cleanly to pinned llama.cpp base
  `9fee29e9435f865ec0b811a783a6471a136d9317`.

Promote the new complete patch. Structured summary and raw rows are under
`../data/2026-08-23-ornith35b-moe-gate-up-*`; the public package remains a
candidate until clean-host replay.
