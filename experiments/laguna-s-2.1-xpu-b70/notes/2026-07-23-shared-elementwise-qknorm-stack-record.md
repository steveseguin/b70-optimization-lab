# Laguna exact shared-elementwise + QKNorm/RoPE stack record

Date: 2026-07-23 America/Toronto

## Result

The preregistered A-B-B-A endpoint crossover passed every quality, causal, and
record gate. The two candidate starts measured **34.55070137147406** and
**33.89498511171744 tok/s** for generated tokens 1-100 after TTFT. The lower
candidate exceeds the current approved **33.438926675602126 tok/s** record
`cmrwot89400gqnz014oodtlbp` by **0.45605843611531327 tok/s
(1.363854888%)**.

All four starts matched the canonical q=1 greedy teacher **13/13** and matched
each other **13/13**. All 52 requests reported `cached_tokens=0`.
Long-then-next passed **2/2** on every leg and the 863-input/512-output
rollover row passed **1/1** on every leg. Every leg used a new service, a
60-second-or-longer device-idle gap separated adjacent legs, and the protocol
allowed no warm-up generation, repeated prompt, retained history, or fifth
run.

The conservative LocalMaxxing value is B2, the lower candidate:
**33.89498511171744 tok/s**. B1 is retained as supporting reproducibility
evidence and is not submitted.

## Frozen treatment

Both arms retained the approved exact eager depth-7 stack:

```text
VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE=1
VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2=1
VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE=1
VLLM_XPU_EXACT_SPEC_ATTN=1
LAGUNA_DFLASH_NUM_SPECULATIVE_TOKENS=7
```

The only A/B difference was:

```text
A control:
  VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE=0
  VLLM_XPU_LAGUNA_M8_QKNORM_ROPE=0

B candidate:
  VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE=1
  VLLM_XPU_LAGUNA_M8_QKNORM_ROPE=1
```

`VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK=0` was fixed off in both arms.

The shared-elementwise half replaces four literal BF16 operations per target
layer with two native operations while preserving their incumbent rounding
boundaries. Its four-card component gate was exhaustive over all 65,280
finite BF16 values for both operations, passed changing random inputs and
post-timing replay, removed exactly **94 launches/cycle**, and saved
**0.699138-0.722866 ms/cycle**.

The separately proven Q/K RMSNorm + RoPE half preserves the incumbent
arithmetic, reduces its isolated launch count from **144 to 48 per target
cycle**, and saved **1.134039 ms/cycle** in the component gate. The endpoint
experiment measured the two exact launch-reduction bundles as one frozen
treatment; component savings were not assumed to add.

## Source and runtime identity

- main-repo freeze during every leg:
  `052193e56454d77154d53e8b2f8987fd0e5a42b6`;
- vLLM:
  `8936aac144929190c1e53f8b8624ca397ce16f5b`;
- XPU kernels:
  `b6076ce1249ffee0e30bee528f4cd15c3bffb234`;
- rebuilt shared `_C.abi3.so` SHA256:
  `126da37b23e5eff6840dd256c90164e3a282469e5fafa27830530e63ff36bce2`;
- runner SHA256:
  `2eb8f37b0a7916b2e72d9a51f393034df722b8408ebd9f02dabe54a7fe5280a2`;
- analyzer SHA256:
  `408cd6948f8e7708b12302b6061011ae2b32c812481574676dfd8f239f0a0714`;
- target revision:
  `4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb`; and
- draft revision:
  `5e07c246915c86dc6920fead03d019989224f2ba`.

Each leg independently hashed all target and draft LFS files, checked the
runtime packages and native libraries, required clean source trees, captured
the full benchmark-sensitive environment, began with zero DFlash/request
metrics, and ended with a bounded shutdown plus four-device idle proof.

## Endpoint results

| Leg | Arm | Headline tok/s | p10 / mean | Target-cycle ms | Acceptance |
| --- | --- | ---: | ---: | ---: | ---: |
| A1 | control | 32.826917 | 25.939402 / 38.210676 | 92.438227 | 4642/12040 |
| B1 | candidate | **34.550701** | 27.030435 / 39.694340 | **88.948299** | 4642/12040 |
| B2 | candidate | **33.894985** | 27.232460 / 39.662490 | **88.886261** | 4642/12040 |
| A2 | control | 33.273435 | 25.979233 / 37.828210 | 92.901753 | 4643/12033 |

B1 versus A1:

- headline: **+5.251131%**;
- candidate row wins: **12/13**;
- paired median: **+4.210640%**;
- normalized target-cycle saving: **3.489928 ms**; and
- acceptance-rate difference: **0.000000 percentage points**.

B2 versus A2:

- headline: **+1.868008%**;
- candidate row wins: **13/13**;
- paired median: **+4.224622%**;
- normalized target-cycle saving: **4.015493 ms**; and
- acceptance-rate difference: **-0.030739 percentage points**, within the
  preregistered absolute 0.10-point work-drift bound.

Both adjacent comparisons independently clear every causal gate. The lower
candidate also exceeds the lower control, so the result does not rely on
choosing a favorable start.

## Evidence

Canonical artifact root:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/shared-elementwise-qknorm-stack-abba-8936aac-b6076ce-052193e-20260723T063914Z
```

Key audit hashes:

```text
59922f66bd27133d653843b9c9cdf7ca8c1b95519997354cae9fe71075a475fe  full-analysis.json
94461927f358d4809032b808c0effa2db6d9b4b56704c8a672e378cfd744c8ab  all-vs-canonical-teacher.json
788291299ec9416711d8867b92f6538265941b1fb92021b0357a12447102d144  cross-leg-exactness.json
456d7404fc04615e88409d35e0ca8a18eb646389cea5a836727e8aed3cf76808  03-B2-candidate/bench.json
```

The compact tracked packet is:

```text
data/laguna-s-2.1-shared-elementwise-qknorm-stack-record-20260723.json
```

The LocalMaxxing queue is:

```text
data/localmaxxing-laguna-s-2.1-int4-b70-dflash-shared-elementwise-qknorm-33.895tok-20260723.queue.json
```

The public API was rechecked immediately before staging: the matching approved
4x B70 Laguna INT4 record remained `cmrwot89400gqnz014oodtlbp` at
`33.43892667560213 tok/s`.

## Disposition

This is a strict record candidate. Submit only the lower B2 value after the
queue passes the local policy preflight and an independent identity/payload
audit. Preserve both selectors default-off until the result and reproduction
recipe are promoted together.

No held-out DeepSeek pack, cache/history acceleration, repeated prompt, or
`/mnt/fast-ai` artifact was used. Postflight left no endpoint or worker
running and all four B70s free.
