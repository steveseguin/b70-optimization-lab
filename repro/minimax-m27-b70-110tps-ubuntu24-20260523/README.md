# MiniMax M2.7 INT4 on Ubuntu 24.04 with 4x Intel Arc Pro B70

This folder documents a fresh Ubuntu 24.04 bring-up performed on 2026-05-23 for:

- Model: `Lasimeri/MiniMax-M2.7-int4-AutoRound`
- Hardware: 4x Intel Arc Pro B70 32 GB
- Serving API: vLLM OpenAI-compatible endpoint
- Served max context: `32768` tokens by default
- Benchmark/quality context used for the comparable speed gate: `2048`
- Benchmark shape: prompt 512, output 1536, tensor parallel 4
- Quality status: strict gates passed
- Mean total/effective throughput: `110.896 tok/s`
- Mean output-only throughput: `83.172 tok/s`
- OpenAI endpoint warm decode check: about `83.8 output tok/s`
- OpenAI endpoint prompt/prefill check: about `1.7k-1.8k prompt tok/s`

The run satisfies the user's requested `>90 tok/s` effective total throughput,
but it is not a new output-token speed record. Earlier repo memory files mention
an 89-class strict lane and a later 94-class structured lane. This 2026-05-23
setup is valuable because it is deployable, quality-gated, OpenAI-compatible,
serves roughly 32k context, and is documented from a mostly fresh machine state.

## Plain-English Summary

The Intel Arc Pro B70 is a workstation GPU. Four of them can run a large quantized MiniMax model locally if the software stack is aligned carefully:

1. Ubuntu needs Intel's current GPU userspace packages and oneAPI compiler.
2. PyTorch must be the XPU build, not regular CUDA or CPU PyTorch.
3. vLLM needs local Intel/XPU patches from this repo.
4. The MiniMax INT4 MoE path needs llm-scaler custom kernels.
5. Native XPU extensions must be compiled against the exact PyTorch ABI in the venv.
6. Quality must be tested before speed numbers are trusted.

This is not a one-command consumer install yet. It is a reproducible lab setup for people and agents who are comfortable running shell scripts, reading logs, and rebooting when drivers change.

## Minimum Assumptions

The scripts are written for:

- Ubuntu 24.04.x on x86_64.
- Four Intel Arc Pro B70 GPUs installed and visible on PCIe.
- At least 512 GB SSD/NVMe storage.
- At least 16 GB system RAM.
- Network access for apt, GitHub, PyPI/PyTorch, and Hugging Face.
- Optional Hugging Face token if the model repo or download quota requires it.

The native `vllm-xpu-kernels` source build can use more than 120 GB resident memory for one compiler process. On machines with 16-64 GB RAM, use a temporary swap file on SSD. The provided build script creates one by default and removes it when the build finishes.

## Disk Budget

Plan for roughly:

- Model weights: `113 GB`
- Hugging Face cache: `100-140 GB` during download unless cleaned
- vLLM/llm-scaler/vllm-xpu-kernels source and build trees: `20-80 GB`
- Torch compile caches and benchmark outputs: `10-60 GB`
- Temporary swap for native build: default `160 GB`

512 GB is tight but workable if `/mnt/fast-ai` has most of the space and old build trees/caches are cleaned.

## Current Known-Good Versions

Observed on the working system:

- Ubuntu: `24.04.4 LTS`
- Intel compute runtime packages:
  - `intel-opencl-icd 26.18.38308.1-0`
  - `libze-intel-gpu1 26.18.38308.1-0`
  - `intel-ocloc 26.18.38308.1-0`
  - `intel-igc-core-2 2.34.4`
  - `intel-igc-opencl-2 2.34.4`
  - `libigdgmm12 22.10.0`
  - `libze1 1.28.2-1~24.04~ppa1`
  - `xpu-smi 1.3.6-1~24.04~ppa1`
- oneAPI compiler used for builds: `/opt/intel/oneapi/compiler/2025.3`
- Python: `3.12`
- PyTorch: `2.11.0+xpu`
- vLLM source commit: `c51df43005726a09c6eb7348e8c1b00501c70a8e`
- llm-scaler source commit: `4bfc0070090cc54afdb2d46b8e57882359141568`
- vllm-xpu-kernels source commit: `28e1f5e74c15744b69cf3b760f6160ceabd15de0`

Important: source `/opt/intel/oneapi/compiler/2025.3/env/vars.sh` for builds. On this machine, using the umbrella `/opt/intel/oneapi/setvars.sh` selected oneAPI 2026 and caused SYCL header/build trouble.

## Fresh-System Quick Start

Clone this repository:

```bash
git clone https://github.com/steveseguin/llm-optimizations.git
cd llm-optimizations/repro/minimax-m27-b70-110tps-ubuntu24-20260523
```

Install system packages, Intel GPU userspace, and oneAPI:

```bash
sudo bash scripts/00-install-system-deps.sh
sudo reboot
```

After reboot, verify GPUs:

```bash
xpu-smi discovery
clinfo -l
```

Set up storage, download the model, and build the Python/native stack:

```bash
sudo bash scripts/01-prepare-storage.sh

# Optional if needed:
# export HF_TOKEN=...
bash scripts/02-download-model.sh

bash scripts/03-build-stack.sh
```

Verify imports and runtime:

```bash
bash scripts/04-verify-runtime.sh
```

Run the quality and benchmark gate before serving:

```bash
bash scripts/05-run-quality-and-benchmark.sh
```

Start the OpenAI-compatible endpoint:

```bash
bash scripts/06-serve-openai-compatible.sh
```

The serve script listens on `0.0.0.0:8000` and defaults to:

```text
max_model_len=32768
gpu_memory_utilization=0.95
```

Override only if you are intentionally retesting capacity:

```bash
VLLM_MAX_MODEL_LEN=16384 bash scripts/06-serve-openai-compatible.sh
```

From the same machine:

```bash
curl http://127.0.0.1:8000/v1/models
```

From another LAN machine, replace the IP:

```bash
curl http://<server-lan-ip>:8000/v1/models
```

## Expected Results

For this exact setup, the strict gate produced:

- Quality status: `quality_passed`
- Mean total/effective throughput: `110.8962457692952 tok/s`
- Total/effective throughput repeats:
  - `109.82634516832029`
  - `111.29770064350417`
  - `111.0660964054885`
  - `111.39484085986787`
- Mean output-only throughput: `83.1721843269714 tok/s`
- Output-only repeats:
  - `82.36975887624021`
  - `83.47327548262813`
  - `83.29957230411637`
  - `83.5461306449009`

Primary local artifact from the originating machine:

`/mnt/fast-ai/bench-results/minimax-m27-b70-89tps/strict/minimax-repro-minimax-moe-full-forward-customop-plus-output-ar-strict-tp4-ctx2048-mbt512-bs256-20260523T145201Z-summary.json`

### How To Compare 83, 89, 93, and 94 tok/s Notes

Label the benchmark before comparing numbers:

- Current fresh deployable endpoint: about `84.1 output tok/s` warm through the
  OpenAI-compatible API, with a `32768` token served context.
- Older strict random decode lane: `89.314 output tok/s` for p512/n1536,
  context 2048.
- Newer `94` class result: constrained structured-output lane, not the same
  random p512/n1536 decode test.

The current host likely gives up some generated-token throughput because it is
running the B70s over PCIe4 x16 instead of the earlier PCIe5-class path:

- Current link state: `16.0 GT/s`, width 16, or PCIe4 x16.
- B70 advertised max: `32.0 GT/s`, width 16, or PCIe5 x16.
- PCIe5 x16 has about twice the raw signaling rate of PCIe4 x16.
- Older 256 MiB XCCL allreduce reference: about `27.88 GB/s`.
- Current 256 MiB XCCL allreduce: about `13.79 GB/s`.
- `13.79 / 27.88 = 0.494`, so the measured fabric bandwidth is about half.
- `83.8 / 89.314 = 0.938`, so the end-to-end decode rate is about 94% of the
  older strict result.

That lines up in a practical way: a 2x drop in GPU-to-GPU communication
bandwidth causes a smaller end-to-end decode drop because only part of each
generated-token step is communication. The rest is local GPU compute, memory
traffic, vLLM scheduling, and sampling. This is not proof that PCIe explains
everything; the current vLLM source also differs from the older promoted stack.
It is, however, a credible non-quality explanation for why this host lands near
83 instead of the older 89-93 class.

Warm versus cold also matters. Cold runs can include model load, graph capture,
kernel compilation, and cache creation. The older repro saw `69.33 output tok/s`
on a first post-reboot pass and `88.72 output tok/s` on the immediate warm
rerun. Compare warm runs to warm runs.

## Served Context Window

The endpoint was expanded after the strict speed gate. The practical server
default is now `32768` tokens, not `2048`.

Observed on 2026-05-23:

- Before moving display duty off the B70s, `32768` failed vLLM's KV-cache memory
  check and `24576` was the practical default.
- After moving display to the onboard ASPEED VGA adapter and adding
  `xe.disable_display=1`, `32768` started successfully with
  `gpu_memory_utilization=0.95`.
- vLLM reported `33,792` GPU KV-cache tokens and `1.03x` maximum concurrency
  for a 32,768-token request.
- `xpu-smi` showed about `32651 MiB` used per B70 after startup. This is
  expected because vLLM preallocates KV cache memory.
- OpenAI endpoint short decode after warmup: `84.12 output tok/s` for
  prompt 510 / output 1536.
- Later endpoint metrics harness run: `85.45 output tok/s` after first streamed
  chunk, `111.64 total tok/s`, `351 ms` vLLM TTFT, and a conservative
  `1446 tok/s` prefill lower-bound for prompt 510 / output 1536 at the same
  32K served context. See
  `../../data/minimax-m27-openai-endpoint-metrics-32k-20260524.json`.
- Near-full-context API request: `32408` prompt tokens plus `64` generated
  tokens completed without OOM.
- Prompt/prefill checks with `max_tokens=1` measured about `1.7k-1.8k prompt
  tok/s` for 2k-16k prompt sizes. A 16k prompt took about `9 s` before the
  generated token, so long-prompt TTFT is visible even though prefill throughput
  is healthy.
- `33792` was tested because vLLM reported `33,792` GPU KV-cache tokens at the
  32k setting, but it did not expose `/v1/models` within the wait window and is
  not promoted.

Structured result: `results/context-window-20260523.json`

Detailed PCIe/prefill follow-up:

`../../notes/2026-05-23-current-host-pcie4-prefill-check.md`

`../../notes/2026-05-23-b70-display-disable-32768-context.md`

## Quality Gates That Passed

The strict run passed:

- `raw145-n64-exact`
- `raw145-n256-exact`
- `semantic-suite-n64-r2`
- `arithmetic-repeat-n64-r16`
- `extended-sixpack-n64-r2`

Do not publish or trust new speed claims unless these gates pass first. Fast nonsense output is not a valid optimization.

## OpenAI-Compatible API

The vLLM server exposes:

- `GET /health`
- `GET /v1/models`
- `POST /v1/chat/completions`
- `POST /v1/completions`
- `POST /v1/responses`
- `POST /v1/messages`

Working listener from the originating machine:

```text
0.0.0.0:8000
```

Model id:

```text
/mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround
```

Expected `/v1/models` field:

```json
{
  "max_model_len": 32768
}
```

Example request:

```bash
curl -sS http://127.0.0.1:8000/v1/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "/mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround",
    "prompt": "Return only the number 42:\n",
    "max_tokens": 16,
    "temperature": 0
  }'
```

## Bugs and Fixes Found During Bring-Up

- Hugging Face/Xet downloads could wedge with stale connections. Workaround: set `HF_HUB_DISABLE_XET=1` and use a retrying `hf download` loop.
- PyTorch `2.13.0.dev20260520+xpu` loaded the model but failed the quality gate during torch.compile/AOT with `AssertionError: Handler already registered for current_stream`. Workaround: use `torch==2.11.0+xpu`.
- Prebuilt `vllm-xpu-kernels` wheels were ABI-incompatible with the selected stack. Workaround: build `vllm-xpu-kernels` from source after installing PyTorch.
- The source build of `vllm-xpu-kernels` can require more than 120 GB RSS for `paged_decode_xe2.cpp`. Workaround: create temporary SSD swap and build conservatively.
- oneAPI 2026 selected via `setvars.sh` caused build trouble. Workaround: source the 2025.3 compiler env directly.
- The quality wrapper passed `--compilation-config-json`, but the Python quality harness did not accept it. Fix: add a compatibility parser argument.
- A `jq` expression in strict summary generation needed parentheses around the boolean comparison. Fix included in this commit.
- `vllm serve` in this checkout does not accept `--async-engine`. Workaround: remove the stale flag; async scheduling is still enabled by vLLM in this config.
- During server startup, Intel `ocloc` sometimes logged internal compiler errors for a Triton reduction kernel, then the process continued and the server started. Treat this as an Intel compiler/runtime bug to report, but it was not fatal in this run.

## What MiniMax M2.7 Looks Like In This Stack

MiniMax M2.7 here is a quantized MoE model. The heavy path is not a plain dense GEMM workload. The optimized lane depends on:

- INT4 W4A16 expert weights from AutoRound.
- vLLM XPU support and graph capture.
- llm-scaler custom ESIMD kernels for MiniMax MoE decode.
- XCCL/oneCCL communication across four B70s.
- Careful compile/cache behavior.

All 62 MoE layers reported the llm-scaler XPU INT4 decode path during quality and serving startup.

## More Details

- Fresh deployment and operator runbook: `../../docs/b70-minimax-ubuntu24-deployment.md`
- Intel-facing notes and asks: `../../docs/intel-b70-minimax-feedback-20260523.md`
- Current agent memory update: `../../AGENT_HANDOFF.md`
