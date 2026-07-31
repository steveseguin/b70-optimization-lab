# Segmented DFlash attention subgraphs

Date: 2026-07-30 America/Toronto

Status: **preregistered before implementation or device execution.**

## Evidence and hypothesis

The exact BF16-KV width-12/depth-11 segmented-DFlash record has now completed
two independent cold legs:

| leg | historical tok/s | preferred 99-interval tok/s |
| --- | ---: | ---: |
| first | 119.189370967 | 117.997477257 |
| confirmation | 119.695499867 | 118.498544868 |

Both are 13/13 token-and-text exact, cache-zero, target 146/145, draft 20/19,
and operationally clean. Capturing the thirteen draft collective boundary
copies was also exact and clean, but measured 119.192374497 / 118.000450752
tok/s and is closed as a throughput route.

The segmented drafter still executes six FlashAttention boundaries eagerly on
every speculative cycle. The existing breakable-graph implementation can
capture an attention boundary into its own subgraph while preserving its
position and caller-owned output buffer. The deployed FA2 binary and attention
library are already the graph-safe local-accessor build previously component-
tested and used for exact width-12 target attention capture:

```text
fa2_binary_sha256=3390a3065de25e06dbe95a8fbc2c8456c3489a2295816782e90a4086aedc9dd4
attn_library_sha256=ad0eb26f3b0680fcd54a50de821e9c881524d50ad5361b872f88cb0b333b65ca
```

The candidate replaces each of the six DFlash Python attention submissions
with one bound subgraph replay. It does not capture any collective and does
not enable the rejected whole-drafter graph path.

## Sealed treatment

Add one default-off selector:

```text
VLLM_XPU_LAGUNA_DFLASH_CAPTURE_ATTENTION_GRAPHS=1
```

It is valid only with the exact BF16-KV width-12/depth-11 segmented-DFlash
contract. With the selector enabled:

- only the drafter wrapper receives `capture_attention_graphs=True`;
- the target retains persistent exact-attention metadata and does not enable
  target attention subgraphs;
- all thirteen draft collectives remain eager, in the same order, using the
  same preallocated outputs;
- the six attention bodies write the same caller-owned outputs;
- each preceding outer segment is materialized before attention capture and
  each captured attention is materialized before the next outer segment;
- draft topology remains exactly 20 graphs / 19 eager boundaries and target
  topology remains 146/145 on all four ranks; and
- selector-off behavior remains byte-for-byte on the incumbent source path.

No model weight, projection quantization, BF16 KV semantic, attention
algorithm, tensor expression, collective, target width, DFlash depth,
sampling/rejection rule, prompt, cache policy, or scoring window changes.

## Gates and stop rules

1. Focused offline tests must prove default-off behavior, drafter-only wiring,
   incompatibility checks, unchanged graph-count expectations, and harness
   identity capture.
2. Inspect and preserve the exact patch before device execution.
3. Run exactly one non-scored two-request, 400-token smoke. Require q1-prefix
   exactness, cache-zero, more than 33 cycles per request, normal decaying
   acceptance, target 146/145 and draft 20/19 on every rank, clean teardown,
   and post-idle pass.
4. Any unsupported capture, token mismatch, topology drift, identity failure,
   collective hang, worker leak, or idle failure closes the route. Do not
   retry, probe, reset, reload/unbind the driver, issue FLR, or delete
   shared-memory objects.
5. Only after smoke passes may one cold 13-prompt score run. The first valid
   result stands; do not warm, omit prompts, retry, move work outside the score,
   or cherry-pick starts.

This note makes no correctness or throughput claim for the treatment.
