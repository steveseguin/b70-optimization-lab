# Ornith 1.5 35B-A3B: GDN RMSNorm/SiLU gate fusion

Date: 2026-08-23 EDT

Status: **accepted target-only package increment; +0.78% matched serving**

## Qwen-derived boundary

Ornith uses llama.cpp's `qwen35moe` graph and exposes the same recurrent gated
normalization boundary as Qwen3.5. Each of its 30 recurrent layers applies
RMSNorm independently to 32 rows of 128 GDN outputs, multiplies the learned
`ssm_norm` weight, applies SiLU to the parallel `z` projection, then multiplies
those two results before the quantized output projection.

The existing SYCL path already collapsed RMSNorm plus its weight into one
launch and SiLU plus the gate multiply into another. This default-off
specialization delays the normalization until `z` is ready and performs both
chains in one 32-workgroup kernel. It uses the stock SIMD16 XOR reduction tree,
the same RMS expression, and a volatile FP32 normalization value before the
final `SiLU(z) * normalized` multiply, preserving the graph's rounded
materialization boundary.

The matcher requires the exact 128x32 FP32 shape, `attn_output-N`,
`blk.N.ssm_norm.weight`, and `z-N` identities, SiLU opcode, graph edges,
single-use intermediates, contiguous layout, and layer range. A mismatch
declines to the established two-kernel path. The increment removes one launch
from each recurrent layer: 30 launches per decoded token, bringing the
complete nine-feature stack to 630 removed launches/token.

## Performance

One B70, local SHA-verified GGUF, F16 KV, flash attention, graph off, target
only. All arms used the same final candidate library SHA-256
`d75d5f1d07b6ac64421bbc9ae3cda7b916584f0422d512f57843a50427478e8c`.

| Protocol | Controls | Candidates | Mean delta |
| --- | --- | --- | ---: |
| `llama-bench p0/n128/d0/r7`, mirrored A/B/B/A | `121.283795`, `121.291096` | `121.576013`, `121.820801` | **+0.34%** |
| fresh 12-prompt server suite, A/B/B/A | `116.692228`, `116.378530` | `117.856453`, `117.035855` | **+0.78%** |

Both candidates exceeded both controls in both protocols. Every server process
used 12 unique prompts once, reported `cached_tokens=0` on every row, and
passed the required tokens 1-100 and final-response gates. The current patch's
directly measured fresh-server mean is `117.446154 tok/s`; it is not derived by
adding the percentage to an earlier operating point.

## Correctness

- Same-final-binary forced 128-token control and candidate transcripts were
  byte-identical and both hashed to
  `d25039a7a21fccc7eaf5f9414803f80c1e3b58cc900ad8034448df8edb57e38c`.
- Candidate execution recorded exactly 3,810 hits: 30 recurrent layers across
  127 decoded graph evaluations.
- Candidate engine runs recorded 26,910 hits apiece; both server runs recorded
  183,960, establishing that the measured path executed throughout each arm.
- The candidate passed 8x repeat stability, arithmetic, exact-copy, and JSON
  schema canaries.
- The complete patch applies cleanly to pinned llama.cpp base
  `9fee29e9435f865ec0b811a783a6471a136d9317`.

Promote the new complete patch. Structured summary, raw engine/server records,
exactness, logs, and canaries are under
`../data/2026-08-23-ornith35b-gdn-rms-gate-*`; the standalone incremental patch
is under `../patches/llamacpp-ornith15-gdn-rms-silu-gate-positive-20260823.patch`.
