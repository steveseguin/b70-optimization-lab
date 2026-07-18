# DSpark Exact-M7 Cycle Profile And Fusion Closure

Date: **2026-07-18**

Status: **exact timeline captured; sampler replay and context-WKV fusion closed
without promotion**

## Result

The qualified DeepSeek V4 Flash K160 DSpark7 record remains **64.661411
tok/s** for one active generation on four B70s. No result in this follow-up
beat that record, so there is no LocalMaxxing submission.

The follow-up replaced the previous inferred overhead bucket with named,
measured DSpark stages. The largest eager draft-side host scope is the Markov
sampler at approximately **10.50 ms/cycle**. A separate reusable breakable
sampler graph remains exact, but it still contains 83 kernels and 14/15
collective breaks and reaches only **62.460903 tok/s**. It does not remove the
work or the coordination that dominates the scope.

A second candidate fused the three DSpark context WKV projections into one
offline-loaded projection. It reduced the context-KV host scope from a
four-rank median of **1.914 ms** to **1.303 ms**, a measured **0.611 ms/cycle**
substage saving. All exact canaries passed before and after both realistic
suites. Complete endpoint medians were nevertheless **64.269762** and
**64.244449 tok/s**, below the record. The candidate remains default-off as a
source and profiling artifact; it is not part of the promoted launcher.

## Exact Identity

- target: unchanged uniform-K160 DeepSeek V4 Flash, revision
  `7c360e1cd4a5168099dbc54d16d929bf6df04990`;
- draft: official three-stage DSpark pack, revision
  `aa22cb07426656189b2573b8e77a9b7333b8ae0f`;
- topology: TP4+EP, four physical Intel Arc Pro B70s, concurrency one;
- target graph: PIECEWISE; draft graph: private breakable PIECEWISE at exact
  query width M=7; target verifier width M=8;
- XPU kernels: `0b99fc5360141d4dd6174fb15f30ec80c74c4d47`;
- oneCCL: `48fda4f0e074db005596d6899d5227d3f0316c12`, with the qualified
  131,072-byte SYCL all-reduce size route;
- prefix caching disabled and every realistic request reports
  `cached_tokens=0`.

The diagnostic vLLM history is deliberately preserved:

- `e19c19f4c1071182d6c772416955f70e936b31f7`: named DSpark profiler
  scopes;
- `7b662885ec525fa7f65df230f301265ad011f5a0`: combined model/sampler
  graph attempt, correctness-rejected;
- `6afa41e757a81fcc20439ebf396701833b969178`: isolated sampler graph;
- `3bee42b45504fd8887ad827646d7d17368128e7c`: isolated graph profiler
  marker;
- `094e030406ec22b0129cccc78bd6442fecd1c0a7`: fused context WKV
  projection;
- `ce70e1921d0d5fc2c456533edc55582e51768be8`: correct fused-scale
  loader mapping and measured candidate identity.

The promoted record remains vLLM `48401ed6a6b8cd4a277bf7b8d64cf53b006bafb1`.

## Measured Stage Map

The baseline trace is a one-request Kineto diagnostic after warmup. Host scope
medians below are medians across the four rank medians:

| DSpark proposal stage | Baseline host ms | Fused-context host ms |
|---|---:|---:|
| combine/copy hidden | 0.854 | 0.892 |
| prepare inputs | 0.477 | 0.496 |
| context KV production/insertion | 1.914 | **1.303** |
| dispatch and metadata | 2.501 | 2.537 |
| three-layer draft backbone | 4.221 | 4.356 |
| Markov sampling | **10.496** | 10.847 |

The fused diagnostic's complete V2 host scopes are approximately 15.49 ms
target forward, 2.05 ms target sample, and 20.79 ms DSpark proposal at the
median rank. These are useful boundary measurements, not additive endpoint
wall time: Kineto distorts oneCCL timing and ranks overlap. The trace parser
therefore excludes oneCCL device duration and does not use cross-device
timestamps to claim arrival skew.

Raw evidence:

- baseline stage trace:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark7-exactm7-stage-profile-20260718T132851Z`;
- isolated sampler graph service:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark7-xpu-exactm7-isolated-samplegraph-20260718T1340Z`;
- isolated sampler graph trace:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark7-exactm7-isolated-samplegraph-stage-profile-20260718T1343Z`;
- fused context-WKV service:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark7-xpu-exactm7-fused-context-wkv-r2-20260718T1355Z`;
- fused context-WKV trace:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark7-exactm7-fused-context-wkv-stage-profile-20260718T1357Z`.

## Correctness Findings

Putting the model and sequential sampler into the same breakable graph was
not safe. The run under
`dspark7-xpu-targetpw-draftpw-exactm7-samplegraph-20260718T1335Z` recorded
duplicated output (`cobalt-forestforest-7291`) and malformed repeated JSON.
This is rejected correctness evidence, even though graph construction itself
succeeded.

Isolating the sampler in its own graph repaired exact output. Six pre-run and
six post-run canaries passed, including changed-input replay, copy, fact, and
strict JSON. Performance still fell to 62.460903 tok/s median with 58.876640
p10. Profiling shows why: the isolated graph's sampler scope is 10.816 ms at
the median rank versus 10.496 ms eager. The graph preserves essentially the
entire kernel and collective structure, so replay adds management without
removing the dominant work.

The fused context-WKV candidate passed all 18 ordered exact checks across its
pre, post-suite-one, and post-suite-two gates. Both 12-prompt realistic suites
passed the fresh-response gate, every row was cache-zero, and all target
outputs remained exact. It is rejected only on endpoint performance.

The first fused loader attempt is also preserved under
`dspark7-xpu-exactm7-fused-context-wkv-20260718T1350Z`. It stopped before
serving with `KeyError: model.context_wkv.scale` because the synthetic merged
module names its FP8 scale parameter `weight_scale_inv`. Commit `ce70e1921`
maps each official stage scale to that actual destination and is the identity
that loaded and passed the gates. This was a loader-name repair, not an
arithmetic relaxation.

## Why The Fusion Did Not Become A Record

The projection fusion did what it was designed to do, but it attacked only a
small part of the cycle. It saves roughly 0.61 ms inside a roughly 20.8 ms
draft proposal while the Markov sampler alone remains about 10.5-10.8 ms.
Small shifts in target-forward time, collective coordination, and prompt
acceptance can consume that saving. Two complete suites are more authoritative
than the isolated substage win, and neither suite beat 64.661411 tok/s.

This is an important closure: repeated vLLM graph wrapping or another
context-only micro-fusion is not a credible route from 64.7 to 100 tok/s. The
next implementation must eliminate sampler/acceptance coordination and other
whole-cycle boundaries, not merely put an existing eager sequence inside a
new replay object.

## Decision And Next Boundary

Keep the following off in the record lane:

- `VLLM_XPU_DSPARK_PIECEWISE_SAMPLE_GRAPH=0`;
- `VLLM_XPU_DSPARK_FUSED_CONTEXT_WKV=0`.

The next high-ceiling work belongs in the fixed-geometry Intel decoder shell:

1. make DSpark sampled IDs, rejection counts, and accepted-prefix commit
   device-resident at fixed addresses;
2. replace the 83-kernel sequential sampler/collective sequence with a
   purpose-built Xe2 operation or a small fixed command-list pipeline;
3. connect it directly to the existing exact M=4/M=8 verifier shell and
   segmented-safe TP4 communication;
4. gate the complete cycle against the frozen realistic and longer-context
   held-out suites before any policy or confidence tuning.

Further generic graph toggles, context-only fusion, or favorable-prompt
selection are closed. A new vLLM-side candidate should require a conservative
whole-cycle ceiling above 0.50 ms and must still beat the endpoint record.
