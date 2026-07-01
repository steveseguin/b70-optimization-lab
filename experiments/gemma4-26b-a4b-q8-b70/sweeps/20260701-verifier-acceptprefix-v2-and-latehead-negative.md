# 2026-07-01 Verifier Follow-Ups: Accept-Prefix v2 and Late-Head Fused Bonus

Status: valid strict128 screens, both closed negative. Do not full512-confirm
or submit.

## Why

The current promoted Gemma 4 26B Q8 lane is still verifier/speculation-bound.
Two bounded follow-ups were checked after the accept-prefix audit:

1. replace the serial accept-prefix Q8 verifier prototype with a multi-row
   argmax plus a tiny device prefix-mask kernel;
2. test the remaining small bonus-preserving flag pair,
   `LLAMA_SPEC_VERIFY_LATE_HEAD_BONUS=1` +
   `LLAMA_SPEC_HEAD_FUSED_OUTPUT_ARGMAX=1`.

Both preserve target/verifier quality: target model remains
`gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`; the Q4_0 MTP draft is accepted only
through target verification.

## Patch

Pre-edit dirty-source snapshot:

- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260701-acceptprefix-v2-preedit-source.patch`

Focused failed patch:

- `patches/gemma4-26b-a4b-q8-b70/20260701-acceptprefix-v2-multirow-mask-negative.patch`

The v2 patch was intentionally reverted after testing, because it lost badly.
The active source tree should not carry it forward.

Implementation idea:

- keep the existing `LLAMA_SPEC_VERIFY_ACCEPT_PREFIX_ARGMAX=1` graph/API path;
- compute all verifier-row top1 IDs with existing
  `ggml_sycl_mul_mat_vec_q_argmax_multi(..., reordered=true, top2=false, ...)`;
- launch one tiny device kernel that sets sampled rows after the first mismatch
  to `-1`, preserving the accept-prefix sampled-ID contract.

This removes the serial per-row Q8 output projection, but it also removes the
only possible row-computation saving. Result: semantically valid, but not a
record lever.

## Run Identity

Common screen identity:

- source: `/home/steve/src/llama.cpp-gemma-record-repro-c926`,
  llama.cpp `c926ad098`, dirty Gemma record stack;
- target/verifier: `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft: `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf`;
- runner: `repro/gemma4-26b-a4b-q8-b70/run-vdr2-selecteddown-record.sh`;
- strict fresh-response gate: fixed realistic suite, each prompt once, cold,
  `cached_tokens=0`, no prompt/cache/history reuse, `MAX_TOKENS=128`,
  primary metric median tokens 1-100 after TTFT;
- common promoted flags: VDR2 selected-down, backend/bulk sampled argmax IDs,
  MTP fused output argmax, draft direct argmax unroll 7, target h_nextn defer,
  f16 KV.

## Results

All rows passed:

- `bench_rc=0`;
- `fresh_response_validity.valid=true`;
- `cached_tokens_all_zero=true`;
- realistic final gate;
- canary `128/128` rows.

| Lane | GPU | Flags | Median tok/s 1-100 | p10 | Mean | Median full-output tok/s | Result |
| --- | ---: | --- | ---: | ---: | ---: | ---: | --- |
| same-binary control | 0 | baseline | `118.88709701458734` | `102.77551898634547` | `116.94435786124306` | `116.407690426329` | reference only |
| accept-prefix v2 | 1 | `LLAMA_SPEC_VERIFY_ACCEPT_PREFIX_ARGMAX=1` | `101.16402021483154` | `90.92844298475613` | `99.87877269338314` | `97.97908237468441` | closed negative |
| late-head fused SPEC_HEAD | 2 | `LLAMA_SPEC_VERIFY_LATE_HEAD_BONUS=1`, `LLAMA_SPEC_HEAD_FUSED_OUTPUT_ARGMAX=1` | `112.1077339459869` | `102.48059033584207` | `112.88954921462887` | `109.98599681407649` | closed negative |

Artifacts:

- `data/gemma4-q8-gpu0-acceptprefix-v2-control-strict128-20260701T0303Z/summary.json`
- `data/gemma4-q8-gpu1-acceptprefix-v2-strict128-20260701T0303Z/summary.json`
- `data/gemma4-q8-gpu2-latehead-fusedspechead-strict128-20260701T0308Z/summary.json`

Note: the summary harness did not yet copy
`LLAMA_SPEC_VERIFY_ACCEPT_PREFIX_ARGMAX` into `launcher_identity` for this run.
The server log does contain `LLAMA_SPEC_VERIFY_ACCEPT_PREFIX_ARGMAX=1`:

- `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu1-acceptprefix-v2-strict128-20260701T0303Z.server.log`

The harness was fixed after the run to record
`launcher_identity.llama_spec_verify_accept_prefix_argmax` going forward.

## Decision

Closed negative:

- accept-prefix v2 is much better framed than the serial prototype, but it
  still loses by `17.72 tok/s` versus the same-binary strict128 control and is
  below the `123.67689864739785 tok/s` valid headline record;
- late-head fused SPEC_HEAD also loses by `6.78 tok/s` versus control.

Do not promote either path and do not submit to LocalMaxxing.

## Implication

The small verifier knobs are now effectively exhausted. Further short-decode
progress likely needs a deeper verifier redesign rather than another flag
combination:

- a verifier path that actually avoids target rows before LM-head work, without
  per-row serial kernels;
- or a different draft/verifier arrangement that raises accepted tokens per
  target forward while preserving Q8 target verification and the fresh-response
  validity gate.
