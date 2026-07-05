# 2026-07-05 Qwen27 GGUF Cache-Off / Selector Refresh

## Question

Could the `Qwen3.6-27B-UD-Q4_K_XL.gguf` llama.cpp/SYCL lane be a legitimate
shortcut past the current Qwen27 vLLM record after fixing the B70 device
selector and strict cache-off defaults?

## Setup

- Model:
  `/mnt/usb-models/models/qwen36-27b-mtp-gguf/Qwen3.6-27B-UD-Q4_K_XL.gguf`
- SHA256:
  `4085665ee36d82a672a238a43f0e5643f2f0e39f2d7bd5d373f0ef10ecf53095`
- Runtime: `/home/steve/src/llama.cpp/build-sycl-b70-qwen36-mtp/bin/llama-server`
- llama.cpp: `fdb1db877`, version `9860`, IntelLLVM `2026.0.0`
- Hardware: one Intel Arc Pro B70 per replica
- Suite: `repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json`
- Validity: each prompt once as a cold response, `cache_prompt=false`,
  server `--cache-ram 0`, no n-gram/history/cache/checkpoint reuse,
  `cached_tokens=0` verified on every request.

Harness fixes made before the run:

- `scripts/serve-qwen36-27b-mtp-gguf-llamacpp.sh` and
  `scripts/serve-rapid-llamacpp-model.sh` now default to
  `ONEAPI_DEVICE_SELECTOR=level_zero:*` plus `ZE_AFFINITY_MASK=$GPU_INDEX`.
  In a fresh shell, `level_zero:$GPU_INDEX` can fail device discovery while
  the wildcard selector plus affinity mask works.
- `scripts/bench-qwen36-27b-mtp-gguf-realistic.sh` and
  `scripts/run-qwen36-27b-mtp-gguf-candidate.sh` now default request JSON to
  `{"cache_prompt":false}`.

## Commands

One-off MTP3 refresh:

```bash
cd /home/steve/llm-optimizations
MODEL=/mnt/usb-models/models/qwen36-27b-mtp-gguf/Qwen3.6-27B-UD-Q4_K_XL.gguf \
MODEL_ALIAS=qwen36-27b-udq4xl-gguf-mtp3 \
LABEL=qwen36-27b-udq4xl-gguf-llamacpp-mtp3-faon-cacheoff-qwensuite128 \
GPU_INDEX=0 PORT=19430 \
LLAMA_SERVER=/home/steve/src/llama.cpp/build-sycl-b70-qwen36-mtp/bin/llama-server \
SUITE=/home/steve/llm-optimizations/repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json \
OUT_DIR=/home/steve/llm-optimizations/data/qwen36-27b-mtp-gguf-q4-b70-baselines \
CTX_SIZE=4096 BATCH_SIZE=1024 UBATCH_SIZE=256 FLASH_ATTN=on CACHE_TYPE_K=f16 CACHE_TYPE_V=f16 \
ONEAPI_DEVICE_SELECTOR='level_zero:*' ZE_AFFINITY_MASK=0 \
EXTRA_LLAMA_ARGS='--cache-ram 0 --spec-type draft-mtp --spec-draft-n-max 3 --spec-draft-n-min 0 --spec-draft-p-min 0.00' \
scripts/run-rapid-llamacpp-realistic-candidate.sh
```

Four-GPU depth screen:

```bash
MODEL=/mnt/usb-models/models/qwen36-27b-mtp-gguf/Qwen3.6-27B-UD-Q4_K_XL.gguf \
MODEL_ALIAS=qwen36-27b-udq4xl-gguf \
BASE_LABEL=qwen36-27b-udq4xl-gguf-llamacpp-mtp-depth-screen-cacheoff-qwensuite128 \
PORT_BASE=19670 \
LLAMA_SERVER=/home/steve/src/llama.cpp/build-sycl-b70-qwen36-mtp/bin/llama-server \
SUITE=/home/steve/llm-optimizations/repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json \
OUT_DIR=/home/steve/llm-optimizations/data/qwen36-27b-mtp-gguf-q4-b70-baselines \
CTX_SIZE=4096 BATCH_SIZE=1024 UBATCH_SIZE=256 FLASH_ATTN=on CACHE_TYPE_K=f16 CACHE_TYPE_V=f16 \
VARIANTS=$'nospec|4096|1024|256|50|--cache-ram 0\nmtp3|4096|1024|256|50|--cache-ram 0 --spec-type draft-mtp --spec-draft-n-max 3 --spec-draft-n-min 0 --spec-draft-p-min 0.00\nmtp4|4096|1024|256|50|--cache-ram 0 --spec-type draft-mtp --spec-draft-n-max 4 --spec-draft-n-min 0 --spec-draft-p-min 0.00\nmtp5|4096|1024|256|50|--cache-ram 0 --spec-type draft-mtp --spec-draft-n-max 5 --spec-draft-n-min 0 --spec-draft-p-min 0.00' \
scripts/run-rapid-llamacpp-fourway-screen.sh
```

## Results

| Row | Gate | Median tok/s | p10 | mean | TTFT ms | Evidence |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| one-off MTP3 refresh | pass, cached zero | `30.81175134560796` | `27.981997135548966` | `30.66817199887896` | `419.0111509524286` | `data/qwen36-27b-mtp-gguf-q4-b70-baselines/qwen36-27b-udq4xl-gguf-llamacpp-mtp3-faon-cacheoff-qwensuite128-20260705T224527Z.json` |
| four-way no-spec | pass, cached zero | `23.674661089513574` | `23.423961126648262` | `23.645717983297775` | `411.0360319027677` | `data/qwen36-27b-mtp-gguf-q4-b70-baselines/qwen36-27b-udq4xl-gguf-llamacpp-mtp-depth-screen-cacheoff-qwensuite128-nospec-20260705T224725Z.json` |
| four-way MTP3 | pass, cached zero | `29.51449755233567` | `26.606570644334624` | `29.71768063055146` | `423.1553884455934` | `data/qwen36-27b-mtp-gguf-q4-b70-baselines/qwen36-27b-udq4xl-gguf-llamacpp-mtp-depth-screen-cacheoff-qwensuite128-mtp3-20260705T224725Z.json` |
| four-way MTP4 | pass, cached zero | `28.599074091462942` | `24.305054323414` | `28.00531313224054` | `422.71748650819063` | `data/qwen36-27b-mtp-gguf-q4-b70-baselines/qwen36-27b-udq4xl-gguf-llamacpp-mtp-depth-screen-cacheoff-qwensuite128-mtp4-20260705T224725Z.json` |
| four-way MTP5 | pass, cached zero | `24.904061199288194` | `22.470958269533675` | `25.056525530366432` | `423.87354152742773` | `data/qwen36-27b-mtp-gguf-q4-b70-baselines/qwen36-27b-udq4xl-gguf-llamacpp-mtp-depth-screen-cacheoff-qwensuite128-mtp5-20260705T224725Z.json` |

The MTP3 server log reports per-request draft acceptance roughly `0.51-0.77`
with mean draft length around `2.5-3.3`, so MTP is working and target-verified.
The target path is simply too slow in this backend for this checkpoint.

## Conclusion

This refresh confirms the 2026-07-03 conclusion:

- llama.cpp MTP helps the GGUF row (`~30.8` vs `~23.7 tok/s`);
- deeper MTP (`n_max=4/5`) loses acceptance and throughput;
- all rows are strict/fresh/cached-zero and valid as reference measurements;
- none are competitive with the current Qwen27 vLLM AutoRound best
  (`65.27648650325429 tok/s` for `webhie/Qwen3.6-27B-int4-AutoRound + runtime
  INT8 LM-head (BF16 scales)`).

Do not spend more time on config-only GGUF tuning for this model. Reopen this
lane only for a real source-level llama.cpp Qwen/GDN/SYCL mechanism or a
materially different GGUF quant/backend.
