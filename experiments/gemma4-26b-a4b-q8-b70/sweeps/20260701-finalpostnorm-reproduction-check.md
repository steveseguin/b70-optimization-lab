# 2026-07-01 Final Postnorm Record Reproduction Check

Goal: verify that the promoted Gemma 4 26B A4B Q8 one-B70 realistic-suite
record remains reproducible after the LM-head/Q8 one-column subgroup experiment
and the oneAPI build-environment repair.

## Build / Environment Note

The active `llama-server` binary is:

`/home/steve/src/llama.cpp-gemma-record-repro-c926/build-sycl-b70-aot-bmg-g31-q8reorder-vdr2/bin/llama-server`

Direct execution from an unsourced shell fails to find Intel runtime libraries
such as `libsvml.so`. This is the same build-environment issue seen during the
LM-head subgroup rebuild: the build/runtime shell needs the Intel oneAPI
environment. The benchmark launcher sources `/opt/intel/oneapi/setvars.sh`
inside `scripts/run-gemma4-26b-llamacpp-replica.sh`, so the reproduction runs
below used the correct runtime environment.

## Exact Promoted Identity

- target/verifier: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft: `gemma-4-26B-A4B-it-Q4_0-MTP.gguf`, accepted tokens verified by the
  Q8 target;
- llama.cpp source/build: `c926ad098`, reordered-Q8 VDR2 build;
- `FLASH_ATTN=on`, `CTX_SIZE=32768`, `GGML_SYCL_ENABLE_VMM=1`;
- `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`, `POLL=100`;
- `n_max=3`, `n_min=2`, `p_min=0.0475`, `--ctx-checkpoints 0`;
- `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`;
- `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`;
- `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1`;
- `LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL=1`;
- LM-head one-column subgroup experiment unset
  (`LLAMA_SYCL_Q8_0_LM_HEAD_1COL_SUBGROUPS=<unset>`);
- fixed realistic cold suite, each prompt once, `cached_tokens=0`.

## First Pass: Over-Canary Stress Run

I first ran the recipe with `CANARY_REPEATS=512`, which produces **2048**
canary rows because the canary harness has four cases. This was stricter than
the promoted full512 identity and therefore not an exact reproduction. All
lanes were valid, but the best median stayed below the record.

| GPU | Summary | Canary | Median 1-100 | p10 | Mean | Full512 | Wall | TTFT ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2 | `data/gemma4-q8-gpu2-finalpostnorm-repro-full512-20260701T083817Z/summary.json` | 2048/2048 | 121.76090491291887 | 107.82235235856308 | 119.09324258693259 | 108.55756815222539 | 104.25823859828652 | 178.11117303790525 |
| 0 | `data/gemma4-q8-gpu0-finalpostnorm-repro-full512-20260701T083817Z/summary.json` | 2048/2048 | 117.11799420342673 | 101.09431066634843 | 116.72353451778899 | 111.1425828827702 | 106.50397156492042 | 178.67420351831242 |
| 3 | `data/gemma4-q8-gpu3-finalpostnorm-repro-full512-20260701T083817Z/summary.json` | 2048/2048 | 116.49915664209668 | 104.8596471782931 | 117.17794978247309 | 113.06309470108232 | 108.00076771092027 | 177.8737929998897 |
| 1 | `data/gemma4-q8-gpu1-finalpostnorm-repro-full512-20260701T083817Z/summary.json` | 2048/2048 | 116.39590498908902 | 107.67014066639206 | 117.6536773122761 | 109.92546748884634 | 105.36496673102833 | 178.2805760158226 |

Decision: valid stress evidence, but do not use as the exact reproduction
identity because the canary scale differs from the promoted full512 rows.

## Exact Full512 Reproduction

Re-ran with `CANARY_REPEATS=128`, which matches the promoted full512 canary
scale (`512/512` rows). All four lanes passed the strict realistic gate,
reported `cached_tokens=0` for every prompt, and kept LM-head subgroup unset.

| GPU | Summary | Canary | Median 1-100 | p10 | Mean | Full512 | Wall | TTFT ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | `data/gemma4-q8-gpu0-finalpostnorm-reproexact-full512-20260701T084728Z/summary.json` | 512/512 | **124.97714084813418** | 103.83610041293263 | 122.47435471668817 | 114.87107033590866 | 108.58112847853889 | 178.6938319564797 |
| 3 | `data/gemma4-q8-gpu3-finalpostnorm-reproexact-full512-20260701T084728Z/summary.json` | 512/512 | 121.59076340768573 | 104.50400885221863 | 119.03125200950848 | 109.19763273644445 | 104.77880134808416 | 178.3311164798215 |
| 1 | `data/gemma4-q8-gpu1-finalpostnorm-reproexact-full512-20260701T084728Z/summary.json` | 512/512 | 119.26425148518223 | 104.30812751309528 | 116.4889731039265 | 108.14794679119458 | 103.6186569337255 | 178.77354635857046 |
| 2 | `data/gemma4-q8-gpu2-finalpostnorm-reproexact-full512-20260701T084728Z/summary.json` | 512/512 | 113.63257982764395 | 101.33391203129552 | 114.20740615113683 | 109.84405988518598 | 105.01470816650525 | 178.1337914825417 |

## Decision

The ~124 record **is still reproducible**. The exact-identity GPU0 lane reached
`124.97714084813418 tok/s`, beating the previous `123.67689864739785` row under
the same validity policy:

- fixed realistic prompt suite;
- each prompt sent once;
- `cached_tokens=0` for every request;
- no prompt/KV/context/response reuse;
- no n-gram/history acceleration;
- Q4_0 MTP draft accepted tokens verified by the UD-Q8_K_XL target;
- canary passed `512/512`.

LocalMaxxing accepted the new row as `cmr1u77na01k2ld01kalwzs1e`.

The lane remains high-variance: the exact four-lane batch spanned
`113.6326` to `124.9771` on the primary metric. Treat `124.9771` as the current
valid high and the `119-122` rows as the expected same-recipe support band, not
as evidence that every repeat should hit 124+.
