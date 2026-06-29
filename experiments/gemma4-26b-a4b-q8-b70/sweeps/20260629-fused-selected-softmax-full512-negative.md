# Gemma 4 26B Q8: fused selected-softmax full512 screen

Date: 2026-06-29.

Purpose: promote-check the small strict128 gain from
`LLAMA_GEMMA4_MOE_FUSED_DOWN_SELECTED_SOFTMAX=1` under the full realistic
cold-response gate, and test whether it interacts favorably with
`LLAMA_SPEC_VERIFY_CLIP_DRAFT_AT_EOG=1`.

Current valid record remains
`115.8466634928202 tok/s` median generated-token throughput for tokens 1-100
after TTFT:
`data/gemma4-q8-gpu1-selecteddown-bf16retest-control-full512-20260629T051323Z/summary.json`.

## Harness Hygiene

Before this run, the Gemma harness did not propagate or record
`LLAMA_SPEC_VERIFY_CLIP_DRAFT_AT_EOG`, so older EOG-only runs are useful as
diagnostics but not ideal promotion evidence for that flag. The harness now:

- passes `LLAMA_SPEC_VERIFY_CLIP_DRAFT_AT_EOG` through to the server wrapper;
- echoes it in the server identity log;
- records it in `summary.json` as
  `launcher_identity.llama_spec_verify_clip_draft_at_eog`.

Patch artifact:
`patches/gemma4-26b-a4b-q8-b70/20260629-eog-identity-harness.patch`.

An initial detached `nohup` 4-lane launch at stamp `20260629T194441Z` exited
before benchmark execution and produced only empty readiness artifacts. It is
not result evidence. The real run below used one persistent parent shell so
the benchmark runners and server children stayed alive.

## Run Identity

Common identity:

- model: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- MTP draft: `gemma-4-26B-A4B-it-Q4_0-MTP.gguf`;
- `REALISTIC_GATE=1`, `MAX_TOKENS=512`, `CANARY_REPEATS=128`;
- fixed realistic suite, each prompt once, `cached_tokens=0` every request;
- `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`, graph enabled, VMM off, f16 KV;
- record stack flags: VDR2 selected-down, reordered Q8 direct VDR2,
  F16 p021 small-ncols, backend argmax IDs, bulk sampled IDs, MTP `n_max=3`,
  `n_min=2`, `p_min=0.0475`, `--ctx-checkpoints 0`.

## Results

All four lanes passed validity:

- `fresh_response_validity.valid=true`;
- `cached_tokens_all_zero=true`;
- `realistic_final_gate.passed=true`;
- `canary_pass_all=true`, `canary_rows_completed=512`;
- headline-eligible Q8 target/verifier.

| Lane | Flags | Median 1-100 after TTFT | Delta vs record | p10 | Mean | Full512 after-TTFT median | Wall full512 median | TTFT median |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `data/gemma4-q8-gpu0-fusedselsoft-full512-control-20260629T194706Z/summary.json` | control | 112.21988003325279 | -3.626783459567406 | 99.83204266247577 | 111.3223809280568 | 105.87508696822127 | 102.15958247797198 | 179.97743404703215 ms |
| `data/gemma4-q8-gpu1-fusedselsoft-full512-on-20260629T194706Z/summary.json` | fused selected-softmax | 111.89648891729823 | -3.95017457552197 | 104.04289186416594 | 113.60049869714845 | 105.66422294302444 | 101.57938287906168 | 181.26262404257432 ms |
| `data/gemma4-q8-gpu2-fusedselsoft-eog-full512-on-20260629T194706Z/summary.json` | fused selected-softmax + EOG clip | 111.90908727268967 | -3.9375762201305236 | 104.27650863040606 | 113.72516811706184 | 107.93360996211277 | 102.96396134848032 | 181.28188245464116 ms |
| `data/gemma4-q8-gpu3-fusedselsoft-full512-control-20260629T194706Z/summary.json` | control | 112.99706496186322 | -2.849598530956982 | 104.05982166691435 | 113.68748860363911 | 105.47714696225577 | 101.62498299999388 | 180.16293249092996 ms |

## Decision

Do not promote and do not submit to LocalMaxxing. The candidates are valid
fresh-response runs, but neither beats the current `115.8466634928202 tok/s`
headline record. EOG clip improved the full512 after-TTFT median in this
paired run, but the primary metric is still lower than both the promoted
record and the same-day controls.

The strict128 positive from fused selected-softmax did not survive full512
promotion. Keep the patch default-off as an archived experiment; do not spend
more work on this interaction unless a later profile shows it materially
reduces a new bottleneck.
