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

## Offline implementation

- vLLM base:
  `4f5e7a63cbd0d0bb409207e079421d0d5532d197`;
- branch:
  `experiment/laguna-dflash-attention-subgraphs-20260730`;
- candidate commit:
  `e63b413ea1bbeb8a367ec390e097c478bd84b7ed`;
- worktree:
  `/home/steve/src/laguna-vllm-dflash-attention-subgraphs-20260730`;
- preserved patch:
  `patches/laguna-s-2.1-xpu-b70/0001-xpu-capture-segmented-DFlash-attention-subgraphs.patch`;
- patch SHA-256:
  `76a3295fe4d8295aa83a3a191906785b992c0019cc4a62541d4dd1e5d48b8632`;
- focused wrapper and breakable-graph gate:
  `47 passed, 11 skipped`;
- Ruff lint and formatting, Python compilation, Bash syntax, patch apply, and
  relevant whitespace checks: pass.

The wrapper options are generated in one tested helper: the new selector can
enable attention capture only when segmented DFlash is active, while the
expected outer topology remains 20/19. The measurement harness carries the
treatment as its explicit 31st argument, records it in `identity.txt`, verifies
the live service environment, and rejects it without segmented DFlash.

These are offline results only. The next authorized device action is exactly
one non-scored 400-token smoke.

## Preflight-only harness rejection

The first invocation stopped before service startup or device execution at:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
  laguna-dflash-attention-subgraph-smoke-20260731T032002Z
```

The generic harness default expected an older grouped-GEMM binary. The active
confirmed record binary is
`53f3d2941ce322bcdff1b0463ec6fe72387036ea54d3f602a08d690744b3459f`
and matches both cold segmented record legs and the selected runtime lock. The
harness rejected the mismatch before installing cleanup traps, writing an
identity, or launching vLLM. A fresh invocation pinned that expected hash
explicitly. This is not a device attempt or candidate result.

## Non-scored live smoke: pass

Artifact:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
  laguna-dflash-attention-subgraph-smoke-20260731T032030Z
```

The one authorized device smoke passed:

- both 400-token responses matched their canonical q1 prefixes;
- both reported `cached_tokens=0`;
- request-local draft-cycle counts were 105 and 62;
- accepted-per-position curves were non-flat and decayed from 83 to 6 and
  from 54 to 15;
- draft 20/19 and target 146/145 appeared on all four ranks;
- the graph-safe FA2 launch captured without the historical SYCL scratch error;
- no OOM, device-lost, static-identity, or collective error occurred; and
- formal service stop, worker/listener cleanup, and post-idle interval passed.

This diagnostic emitted no throughput score. The preregistered next action is
one cold 13-prompt scored leg with the same candidate identity.
