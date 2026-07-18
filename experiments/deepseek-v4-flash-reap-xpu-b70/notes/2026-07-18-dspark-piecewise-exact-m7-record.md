# DSpark PIECEWISE Exact-M7 Record

Date: **2026-07-18**

Status: **promoted TP4+EP single-session target-verified record**

## Outcome

The unchanged uniform-K160 target reached **64.661411 tok/s** median for
tokens 1-100 after TTFT on four Arc Pro B70s. The run uses the official
DeepSeek V4 Flash three-stage DSpark draft, seven speculative tokens, a
reusable breakable PIECEWISE draft graph captured at exact query width M=7,
and the proven target verifier at M=8. This is one active generation, not
aggregate throughput.

LocalMaxxing approved the result as `cmrpymqh505mxlg01tzg3e0yl`.

Three independent strict, fresh, fixed-suite runs from one service measured:

| Run | Median tok/s | p10 tok/s | Mean tok/s |
| --- | ---: | ---: | ---: |
| screen | **64.661411** | 56.918029 | 62.977117 |
| confirmation | 61.724506 | 53.671113 | 61.805918 |
| third | 64.275173 | 51.162211 | 62.931273 |

The median of the three suite medians is 64.275173 tok/s. Two of three suites
exceed the preceding 63.851301 tok/s MTP1 record. All 36 realistic requests
were unique, fresh, and cache-zero. The exact six-case canary passed before,
between, and after the suites, including changed-input arithmetic
`1073 -> 437 -> 1073`.

## Why the draft path was initially slow or wrong

The official draft is not a small variation of the K160 target. It is a
three-stage, 256-expert DSpark model. Bring-up required:

- isolating draft configuration so its 256 experts did not overwrite the
  target's 160-expert assumptions;
- supporting the SYCL DSpark context-KV insertion boundary;
- retaining K160's specialized direct path while allowing a correct
  256-expert fallback for the draft;
- fitting approximately 27.48 GiB per rank by using an explicit 120 MiB KV
  cache at model length 256.

Draft-eager execution was correct but left the three-layer draft's dispatch
and synchronization costs outside reusable replay. It measured 55.109521
tok/s median. Monolithic FULL draft replay then produced obvious repeated or
corrupted output and was rejected. The exact unsafe state boundary inside
FULL replay was not proven, so the failure must not be described more narrowly
than the evidence supports.

The first private PIECEWISE attempt also exposed a capture-design error: the
generic graph manager warmed M=1/2/4/8 even though a fixed DSpark7 decode only
queries seven draft rows. Its M=2 warmup entered a target-only router
specialization that correctly rejected the 256-expert draft. The repair was
to capture only the smallest fixed descriptor that can serve the query.

## What fixed it

vLLM commits `e3657ea44`, `07823ba02`, and `48401ed6a` add a private breakable
PIECEWISE graph for the DSpark draft, restrict capture to the fixed query
width, and optionally capture the exact M=7 query rather than padding the
draft to M=8. Target verification remains on the already-proven M=8 path.

The progression was:

| Candidate | Median tok/s | Decision |
| --- | ---: | --- |
| DSpark7, target PIECEWISE / draft eager | 55.109521 | correct baseline |
| DSpark5, target PIECEWISE / draft eager | 53.870809 | rejected; naïve shorter depth loses |
| DSpark7, draft PIECEWISE padded M=8 | 60.518331 | correct reusable replay |
| DSpark7, draft PIECEWISE exact M=7 | **64.661411** | promoted record |

Exact M=7 is 17.33% faster than the draft-eager baseline and 6.85% faster than
the padded-M8 draft graph. It is only 1.27% above the preceding endpoint
record, but it proves the reusable DSpark draft boundary and removes one
entire padded draft row without changing the model, speculative depth, or
target verification.

## Acceptance economics

Across the exact-M7 service's three suites and intervening canaries, the
runtime drafted 10,871 tokens and accepted 3,164 (`29.10496%`) over 1,553
cycles. Mean emitted tokens per cycle were 3.037347. Accepted counts by draft
position were `[1165, 790, 515, 315, 214, 109, 56]`, corresponding to
`[75.016%, 50.869%, 33.162%, 20.283%, 13.780%, 7.019%, 3.606%]` of cycles.
The last two positions have little unconditional value, but the losing fixed
DSpark5 result proves that merely shortening every cycle is not the answer.

## Reproduction identity and evidence

- target: `0xSero/DeepSeek-V4-Flash-180B`, revision
  `7c360e1cd4a5168099dbc54d16d929bf6df04990`;
- target path: `/mnt/fast-ai/llm-models/deepseek-v4-flash-xpu/current-k160`;
- draft source: `deepseek-ai/DeepSeek-V4-Flash`, revision
  `aa22cb07426656189b2573b8e77a9b7333b8ae0f`;
- draft pack: `/mnt/fast-ai/llm-models/deepseek-v4-flash-xpu/dspark-draft-pack-aa22cb0`;
- vLLM: `48401ed6a6b8cd4a277bf7b8d64cf53b006bafb1`;
- XPU kernels: `0b99fc5360141d4dd6174fb15f30ec80c74c4d47`;
- oneCCL: `48fda4f0e074db005596d6899d5227d3f0316c12`, with the 131,072-byte
  SYCL all-reduce route threshold;
- graph identity: target PIECEWISE, draft breakable PIECEWISE exact M=7,
  target verifier M=8;
- strict evidence:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark7-xpu-targetpw-draftpw-exactm7-20260718T0556Z`;
- padded-M8 evidence:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark7-xpu-targetpw-draftpw-fixedwidth-20260718T0552Z`;
- draft-eager evidence:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark7-xpu-piecewise-target-eager-draft-20260718T0644Z`;
- DSpark5 evidence:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark5-xpu-piecewise-target-eager-draft-20260718T0542Z`.

Launch with:

```bash
DSPARK_GRAPH_MODE=piecewise \
DSPARK_DRAFT_GRAPH_MODE=piecewise \
DSPARK_SPEC_TOKENS=7 \
VLLM_XPU_DSPARK_EXACT_QUERY_CAPTURE=1 \
experiments/deepseek-v4-flash-reap-xpu-b70/scripts/serve-k160-dspark-candidate.sh
```

The measured run's base `identity.txt` predates the addition of explicit
DSpark graph-selector fields. Its command line, server log, queue payload, and
launcher stdout preserve those selectors; future runs record them directly in
`identity.txt`.

## Next action

This is the first correct reusable DSpark draft graph on the B70 lane, not the
100 tok/s objective. The next experiment must produce an exact cycle timeline
for target verification, context-KV preparation, draft input preparation,
three-layer draft execution, Markov sampling, queue gaps, and host work.
Prioritize the still-eager context-KV/input-preparation boundary and the
256-expert draft pipeline. A confidence-driven dynamic depth policy is worth
testing only after profiling and only against frozen held-out prompts with
target verification; the official confidence-head weights are not currently
wired, and fixed DSpark5 already lost.
