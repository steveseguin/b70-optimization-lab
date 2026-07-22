# Laguna S 2.1 first LocalMaxxing submission gate — 2026-07-22

## Result first

- Valid exact eager DFlash headline: **31.77427774785138 tok/s median**
  generated-token throughput for tokens 1–100 after TTFT across 13 fixed
  realistic prompts; p10 **25.029106340300842**, mean
  **36.97775395005996**.
- Median TTFT: **5915.868743089959 ms**. Median full-128 response after-TTFT
  throughput: **31.157083310089412 tok/s**. Median wall full-response
  throughput: **13.328968461385802 tok/s**.
- Freshness: **13/13 DFlash requests had `cached_tokens=0`**. Each unique
  prompt was sent once, serially, with one active generation and no prefix,
  prompt/KV, response, checkpoint, or prior-output history reuse.
- Exactness: **13/13 full 128-token DFlash arrays matched** the fresh q=1
  eager target greedy teacher. All 13 teacher requests were also cache-zero.
- Rollover: the realistic repository-patch row had **863 input tokens** and
  128 output tokens; its complete output token array matched q=1.
- Payload staged only, not submitted:
  `data/localmaxxing-laguna-s-2.1-int4-b70-dflash-batchexact-31.774tok-20260722.queue.json`.
- Classification: the 128-token packet is a **fresh exact 13/13 candidate**, but
  the staged payload is **not currently submit-valid under the literal
  full-512 contract**. A fresh full-512 extension failed exactness 12/13. No
  LocalMaxxing API call was made.

## Fixed realistic suite

`experiments/laguna-s-2.1-xpu-b70/realistic-suite-v1.json` now contains 13
unique prompts. It is coding-heavy and covers Python implementation/debugging,
SQL, transaction concurrency, TypeScript, Rust, repository refactoring, shell
safety, arithmetic, protocol prose, structured extraction, an engineering
decision memo, and a long repository-patch rollover task.

Suite SHA-256:

```text
9fdaacfdc4de59407a73cbe0d8130fa0f6abe91fed782e399a58adbc035ea638
```

The first provisional long prompt ended at 81 tokens and correctly failed the
headline harness. It was replaced before the final fixed-suite captures by a
realistic multi-file patch request that produced 128 tokens. Provisional
artifacts remain under the Corsair run root and are not used by the payload.

## Per-prompt headline rows

| Prompt | Prompt tokens | Output tokens | cached_tokens | tok/s 1–100 | TTFT ms |
|---|---:|---:|---:|---:|---:|
| python-lru-cache | 90 | 128 | 0 | 28.418863 | 4857.341 |
| python-debug-window | 132 | 128 | 0 | 52.665512 | 7202.468 |
| sql-sessionization | 110 | 128 | 0 | 38.575730 | 5706.706 |
| concurrency-review | 102 | 128 | 0 | 29.622539 | 5459.291 |
| arithmetic-reasoning | 112 | 128 | 0 | 49.359955 | 5883.509 |
| factual-protocol | 89 | 128 | 0 | 24.325663 | 4781.859 |
| typescript-cancellation | 149 | 128 | 0 | 39.909653 | 7979.591 |
| rust-stream-parser | 111 | 128 | 0 | 28.152780 | 6006.500 |
| repository-refactor-plan | 125 | 128 | 0 | 41.958385 | 6347.072 |
| shell-safety-review | 140 | 128 | 0 | 31.774278 | 7464.699 |
| structured-extraction | 229 | 128 | 0 | 66.371672 | 12169.070 |
| prose-decision-memo | 112 | 128 | 0 | 27.842881 | 5915.869 |
| long-rollover-repository-audit | 863 | 128 | 0 | 21.732890 | 354.887 |

Timing source was `openai_stream_token_ids_chunk_timestamp`; the benchmark
uses cumulative streamed token-ID arrival timestamps, not content-delta counts.

## Exactness evidence

Teacher packet:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/submission-gate-q1-eager-final-4a25d9a-6fc06b0-20260722T125037Z
```

Headline DFlash packet:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/submission-gate-dflash-eager-final-4a25d9a-6fc06b0-20260722T125540Z
```

The DFlash packet contains `bench.json`, `bench.stdout`, `server.log`,
`metrics-after-suite.prom`, and `exactness.json`. The exactness artifact checks
matching prompt hashes, full output token arrays, lengths, output hashes, and
both sides' cached-token values for every prompt.

Post-suite speculative counters were 1,173 accepted tokens from 3,570 draft
tokens (**32.857142857142854%**). These are audit/support counters; the
headline remains the streamed tokens-1–100 suite metric.

## Full-512 manual preflight blocker

The submission helper's scripted dry-run passes the staged 128-token queue, but
`docs/localmaxxing.md` also asks for full-512 throughput. A fresh extension used
the same suite with `max_tokens=512` on fresh q=1 and DFlash servers:

- DFlash diagnostic median/p10/mean for tokens 1–100:
  `31.731120436628586 / 25.021470036554312 / 35.294477525610326` tok/s;
- 11 rows naturally reached 512 tokens; structured extraction stopped at 296
  and the decision memo at 426, without forcing generation past EOS;
- the 11-row full-512 after-TTFT median/p10/mean was
  `40.845545575883214 / 27.640149064565787 / 41.504530568708155` tok/s;
- all 13 q=1 and 13 DFlash requests were fresh and cache-zero;
- complete output exactness was only **12/13**, so this extension is invalid.

The failing `python-debug-window` row diverged at output token 0. Its q=1
512-token output repeated the earlier q=1 prefix, but the DFlash output did not
repeat the exact 128-token DFlash prefix. A separate fresh two-prompt diagnostic
reproduced the failure: after `python-lru-cache` generated 512 tokens,
`python-debug-window` again diverged from q=1 at token 0. This is consistent
with a cross-request long-generation DFlash state-reset bug, not timing noise.

Full-512 evidence:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/submission-gate-q1-eager-full512-4a25d9a-6fc06b0-20260722T130927Z
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/submission-gate-dflash-eager-full512-4a25d9a-6fc06b0-20260722T132103Z
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/full512-cross-request-diagnostic-20260722T132700Z
```

Until this failure is fixed and the complete fixed suite passes again, the
payload must remain staged and must not be submitted.

## Exact runtime identity

- Target: `poolside/Laguna-S-2.1-INT4`, revision
  `4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb`, compressed-tensors INT4
  group-32 W4A16.
- Draft: `poolside/Laguna-S-2.1-DFlash-INT4`, revision
  `5e07c246915c86dc6920fead03d019989224f2ba`. Inspection of
  `model.safetensors` found 69/69 tensors in BF16 and no `quantization_config`;
  it is a BF16 DFlash checkpoint matched/trained for the INT4 target, not an
  INT4-compressed draft.
- vLLM: `4a25d9afbbf71eddbd8edce1815e3b6265c41ab3`, branch
  `experiment/laguna-s-2.1-xpu-bringup-20260721`.
- XPU kernels: `6fc06b08cd10a9e9e7d15e62e1afcf06e7ab6c73`, branch
  `experiment/laguna-s-2.1-fwht-20260721`.
- Native hashes: `_xpu_C.abi3.so`
  `671ce1111b854ca4f3a5275af6d0b701c4dc4b18d78c47f12dfdf10a98bbe103`;
  `_moe_C.abi3.so`
  `f222d3e2d2a8a331e3c85f12e0d02a17aa7a89147bbbcc8ac2c2a816629a405f`;
  `libgrouped_gemm_xe_2.so`
  `285c9bce2001d05b89719645d8afa98a93b589e476fe6e540582009ec90e9f2a`.
- Topology: one TP4+EP4, DP1, PP1 session; `max_num_seqs=1`; BF16 compute and
  KV; NHD KV; max model/batched tokens 8192; block size 64; prefix cache off.
- Exact path: `VLLM_XPU_EXACT_SPEC_ATTN=1` and
  `VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE=1`; DFlash depth 7 / target q=8;
  greedy draft and standard target rejection; deterministic M=1 numerical
  lanes, batched paged-decode verifier attention, fixed-rank BF16 sums, and
  direct deterministic M8 MoE without atomic remap.
- Graph identity: **eager**, with XPU graph, torch.compile, and cudagraphs
  disabled. This is the validated exact candidate identity.
- All model, cache, temp, log, and run writes stayed on CorsairExternal. No
  DeepSeek held-out pack was used and no `/mnt/fast-ai` write was made.

## Why PIECEWISE was rejected

The task initially requested PIECEWISE, but the supplied validated 37.5864
tok/s identity and server log were eager. PIECEWISE therefore received a fresh
gate rather than inheriting the eager exactness claim.

The PIECEWISE DFlash speed suite itself reached 37.76107653387675 tok/s median,
30.377744330458697 p10, and 44.092895471305674 mean with all 13 rows cache-zero.
It is invalid for submission because only **6/13** token arrays matched the
same-suite fresh PIECEWISE q=1 teacher. The rollover row also differed. Two
independent PIECEWISE q=1 server starts disagreed on 4 of the 12 unchanged
provisional prompt arrays, with first differences at output indices 27–58;
their throughput also shifted sharply. PIECEWISE logs recorded repeated IGC
`ocloc` failures for a Triton-compiled kernel before graph capture completed.

Rejected PIECEWISE evidence is preserved at:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/submission-gate-q1-piecewise-final-4a25d9a-6fc06b0-20260722T124113Z
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/submission-gate-dflash-piecewise-4a25d9a-6fc06b0-20260722T124455Z
```

The staged payload accurately describes the eager result and does not claim
PIECEWISE.

## Submission status

The queue file is staged for review only. The local helper's normal dry-run
passes without `--allow-non-headline`, but that helper does not enforce the
documented full-512 evidence clause. Manual preflight therefore blocks this
payload even though scripted preflight passes. The actual LocalMaxxing POST is
not authorized in this task and was not attempted. Claude and the user retain
the submission gate after the full-512 exactness bug is fixed and rerun.
