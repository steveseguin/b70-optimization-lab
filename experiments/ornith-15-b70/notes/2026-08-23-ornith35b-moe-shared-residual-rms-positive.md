# Ornith 1.5 35B-A3B: MoE shared-branch residual/RMSNorm fusion

Date: 2026-08-23 EDT

Status: **accepted target-only package increment; +1.41% matched serving**

## Qwen-derived boundary

Ornith's 40 MoE layers expose the same residual structure that motivated this
lab's earlier Qwen work. Each layer first adds the routed-expert and shared-
expert branches into `ffn_out-*`, then adds the attention residual into
`l_out-*`, and finally applies RMSNorm and its learned weight. The previous
accepted residual/RMSNorm kernel fused only the second add and norm boundary.

This default-off specialization extends that proven path one node backward. It
materializes `ffn_out-*` through its real volatile FP32 graph buffer and
reloads it before the residual add, then materializes and reloads `l_out-*`
before executing the unchanged RMS reduction order and norm-weight expression.
Those stores preserve both graph-visible FP32 rounding boundaries.

The matcher requires the exact Ornith names, two adjacent 2048-element FP32
ADD nodes, contiguous one-token layout, RMSNorm and MUL adjacency, and matching
device buffers. The RMS intermediate must have a single consumer; both ADD
outputs are still materialized for their other graph users. Any mismatch falls
back to the prior stack.

The increment eliminates the first ADD launch in each MoE layer: 40 launches
per decoded token. The complete eight-optimization stack now removes 600
launches/token.

## Performance

One B70, local SHA-verified GGUF, F16 KV, flash attention, target only. All
measurements used final candidate library SHA-256
`78047ec2562261ee3481c6a91d65059af10501e1016ebcc3bdc48cd210934007`.

| Protocol | Controls | Candidates | Mean delta |
| --- | --- | --- | ---: |
| `llama-bench p0/n128/d0/r7`, mirrored | `120.113696`, `120.406444` | `121.084735`, `121.827090` | **+0.99%** |
| fresh 12-prompt server suite | `116.790535`, `116.022431` | `118.592477`, `117.504501` | **+1.41%** |

The fresh-server candidate mean is `118.048489 tok/s`; both candidates beat
both controls. Every process used 12 unique prompts once, prompt caching and
history acceleration were disabled, all rows reported `cached_tokens=0`, and
the required tokens 1-100 window and final gate passed.

## Correctness

- Same-final-binary forced 128-token output was byte-identical; both canonical
  transcripts hashed to
  `d25039a7a21fccc7eaf5f9414803f80c1e3b58cc900ad8034448df8edb57e38c`.
- Door off produced 10,160 prior residual/RMSNorm hits. Door on produced 5,080
  new shared-branch hits plus 5,080 prior residual/RMSNorm hits: exactly 40
  layers across 127 decoded graph evaluations, with no lost coverage.
- Engine and serving candidates showed the expected hit counts.
- The candidate passed 8x repeat stability, arithmetic, exact-copy, and JSON
  schema canaries.
- The complete patch applies cleanly to pinned llama.cpp base
  `9fee29e9435f865ec0b811a783a6471a136d9317`.

Promote the new complete patch. Structured summary and raw rows are under
`../data/2026-08-23-ornith35b-moe-shared-residual-rms-*`; the public package
remains a candidate until clean-host replay.
