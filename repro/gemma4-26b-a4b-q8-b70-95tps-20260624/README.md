# Gemma 4 26B A4B Q8 on B70, 95 tok/s

This is a **superseded historical reproduction recipe** for the verified
Gemma 4 26B A4B single-GPU B70 result from 2026-06-24. The current valid
fresh-response Q8-target record is `124.97714084813418 tok/s`, LocalMaxxing
`cmr1u77na01k2ld01kalwzs1e`; start from
[`../gemma4-26b-a4b-q8-b70-125tps-20260701/`](../gemma4-26b-a4b-q8-b70-125tps-20260701/README.md)
or
[`../../results/gemma4-26b-a4b-q8-b70/reproduce.md`](../../results/gemma4-26b-a4b-q8-b70/reproduce.md)
for current record attempts.

## Result

- Model: `unsloth/gemma-4-26B-A4B-it-GGUF`, target file `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- Target size: `27,636,230,944` bytes
- Speculative draft only: local `Q4_0` quantized Gemma MTP draft, file `gemma-4-26B-A4B-it-Q4_0-MTP.gguf`
- Draft size: `321,126,560` bytes
- Hardware: 1x Intel Arc Pro B70 32 GB, GPU 0
- Host/platform: Supermicro AMD Threadripper PRO 5955WX system, 128 GB DDR4,
  running headless for the submitted result
- OS: Ubuntu 24.04.4 LTS
- CPU/RAM: AMD Ryzen Threadripper PRO 5955WX, 128 GB DDR4
- Runtime: llama.cpp `c926ad09857517978575d6a74d225b463f7417a0` plus the patch in this folder
- Build: SYCL/Level Zero, AOT target `intel_gpu_bmg_g31`
- Benchmark shape: filled-long prompt, requested 512 prompt tokens, actual 588 prompt tokens, 512 output tokens
- Quality gate: `384/384` chat canary before the measured run
- Historical fresh-response headline: `95.26352416631231 tok/s` after TTFT on the first measured request, `cached_tokens=0`
- Repeat support: `95.38558173206405 tok/s` mean after TTFT across 8 measured requests
- LocalMaxxing submission id: `cmqrsupdk000jqr01af3eu6vu`

The supporting run summary and submission payload are in [`results/`](results/).

## Why Q4_0 Appears Here

The `Q4_0` file is not the 26B target model. It is the small Gemma MTP draft
model used by llama.cpp speculative decoding. That draft proposes tokens; the
`UD-Q8_K_XL` target model verifies accepted tokens and remains the final model
for output quality.

This result should be described as:

```text
Q8 target/verifier with Q4_0 MTP draft only
```

It should not be described as a pure Q8 no-draft run, and it should not be
compared against a Q4 target-model benchmark as if they were the same quality
lane. If the goal is to avoid any Q4 auxiliary file, use the older F16 MTP draft
fresh-response result instead; it was slightly slower than this promoted
Q4_0-draft record.

## Caveats

This record is a fresh-response result. The headline number is the first
measured request after the canary gate, not an n-gram, prompt-cache, or history
reuse result. The Q8 target model verifies accepted draft tokens; the Q4_0 file
is used only as the MTP draft model.

Use the patch in this folder as the source of truth for this **historical 95
tok/s recipe** only. Later direct-id/q-only, verifier row-argmax, deferred
`h_nextn`, selected-softmax, weighted-sum, and runtime tuning work did supersede
this record in the main Gemma result packet; those changes are not part of this
older standalone reproduction path.

## Folder Contents

- [`configs/record.env`](configs/record.env): canonical environment and path defaults
- [`patches/llama-cpp-gemma-record-stack-c926ad098-20260624.patch`](patches/llama-cpp-gemma-record-stack-c926ad098-20260624.patch): exact llama.cpp patch used for the clean record stack
- [`scripts/00-build-llama-cpp-record-stack.sh`](scripts/00-build-llama-cpp-record-stack.sh): clone or reuse llama.cpp, check out the pinned commit, apply the patch, and build
- [`scripts/01-prepare-models.sh`](scripts/01-prepare-models.sh): download the Q8 target and prepare the Q4_0 MTP draft
- [`scripts/02-run-record.sh`](scripts/02-run-record.sh): run the canary and benchmark with the promoted settings
- [`results/summary-20260624T081218Z.json`](results/summary-20260624T081218Z.json): original benchmark summary
- [`results/localmaxxing-queue-20260624.json`](results/localmaxxing-queue-20260624.json): submitted LocalMaxxing payload
- [`results/localmaxxing-response-20260624.log`](results/localmaxxing-response-20260624.log): API response for the submitted record

## Quick Start

Run from this directory:

```bash
bash scripts/00-build-llama-cpp-record-stack.sh
bash scripts/01-prepare-models.sh
bash scripts/02-run-record.sh
```

The scripts default to the same local paths used by the verified run:

- llama.cpp worktree: `/home/steve/src/llama.cpp-gemma-record-stack`
- llama.cpp build: `/home/steve/src/llama.cpp-gemma-record-stack/build-sycl-b70-aot-bmg-g31`
- model directory: `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf`
- result directory: repository `data/`

Override any path by exporting the corresponding variable from
[`configs/record.env`](configs/record.env) before running the scripts.
If the default `/home/steve/src/llama.cpp-gemma-record-stack` worktree already
contains active experiment changes, set `LLAMA_CPP_DIR` to a fresh path before
running `scripts/00-build-llama-cpp-record-stack.sh`.

## Exact Record Command

This is the command identity from the promoted 2026-06-24 run:

```bash
ONEAPI_DEVICE_SELECTOR=level_zero:0 \
GGML_SYCL_ENABLE_VMM=0 \
GGML_SYCL_DISABLE_OPT=0 \
LLAMA_SERVER=/home/steve/src/llama.cpp-gemma-record-stack/build-sycl-b70-aot-bmg-g31/bin/llama-server \
MTP_DRAFT_MODEL=/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf \
MTP_DRAFT_FAST_ARGMAX=1 \
MTP_DRAFT_PROFILE=1 \
MTP_BACKEND_SAMPLING=0 \
MTP_N_MAX=7 \
MTP_N_MIN=2 \
MTP_P_MIN=0.12 \
MTP_DRAFT_DEVICE=SYCL0 \
MTP_DRAFT_THREADS=32 \
MTP_DRAFT_THREADS_BATCH=32 \
MTP_EXTRA_ARGS="--ctx-checkpoints 0" \
CTX_SIZE=8192 \
BATCH_SIZE=512 \
UBATCH_SIZE=512 \
POLL=100 \
THREADS=16 \
CANARY_REPEATS=96 \
BENCH_REPEATS=8 \
PROMPT_TOKENS=512 \
MAX_TOKENS=512 \
BENCH_PROMPT_MODE=filled-long \
scripts/run-gemma4-26b-mtp-candidate.sh \
gemma4-q8-gpu0-mtp-n7-draftq40-full-20260624T081218Z
```

## Patch Stack

Apply the patch in this folder on top of llama.cpp
`c926ad09857517978575d6a74d225b463f7417a0`. It touches only:

- `common/sampling.cpp`
- `common/speculative.cpp`

The patch provides the record-stack MTP changes used here: fast draft argmax,
CPU-side drafting cleanup, direct single-sequence batch fill, verifier buffer
reuse, direct sequence range handling, and optional draft profiling. The
promoted run used `LLAMA_MTP_DRAFT_FAST_ARGMAX=1` and
`LLAMA_MTP_DRAFT_PROFILE=1`.

## Model Preparation

The target Q8 GGUF is downloaded by the repository helper
`scripts/download-gemma4-26b-q8-gguf.sh`. The Q4_0 MTP draft is local-derived
from the F16 MTP draft in the same Hugging Face repo:

```bash
llama-quantize \
  /mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/mtp-gemma-4-26B-A4B-it.gguf \
  /mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf \
  Q4_0
```

The preparation script checks the expected file sizes after download and
quantization. It reads the Hugging Face token from the standard local location
through the existing download helper and never prints it.

## Validation

A reproduction should not be promoted unless all of these hold:

- the llama.cpp commit is `c926ad09857517978575d6a74d225b463f7417a0`
- the patch in this folder applies cleanly, or is already applied exactly
- the target Q8 file size is `27,636,230,944` bytes
- the Q4_0 MTP draft file size is `321,126,560` bytes
- the canary reports `384/384`
- the measured request reports `cached_tokens=0`
- the first measured row is near the original `95.2635 tok/s` after TTFT on an otherwise idle B70

## References

- Repository result ledger: [`../../results/gemma4-26b-a4b-q8-b70/README.md`](../../results/gemma4-26b-a4b-q8-b70/README.md)
- LocalMaxxing submission ledger: [`../../results/localmaxxing-submissions.md`](../../results/localmaxxing-submissions.md)
- Experiment note: [`../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260624T0235-mtp-fused-unroll-feasibility.md`](../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260624T0235-mtp-fused-unroll-feasibility.md)
