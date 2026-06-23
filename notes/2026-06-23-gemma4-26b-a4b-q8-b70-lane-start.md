# 2026-06-23 Gemma 4 26B A4B Q8 B70 Lane Start

Goal from user:

- stop Qwen 35B/36B exploration and start Gemma 4 26B A4B;
- run one full model copy per B70, four replicas total, avoiding TP4 PCIe cost;
- use INT8-or-better quality, no INT4 AutoRound default;
- maximize single-session decode at short context first, then 32K;
- keep multimodal as a nice-to-have, not the first blocker;
- preserve notes, patches, prompts, failed attempts, and results.

Initial local findings:

- Four Intel Arc Pro B70 devices are visible through Level Zero:
  `level_zero:0`, `level_zero:1`, `level_zero:2`, `level_zero:3`.
- oneAPI compiler is installed at `/opt/intel/oneapi/compiler/2026.0/bin/icpx`.
- No Gemma 4 26B model file was found locally.
- No `llama-server`, `llama-cli`, or `llama-bench` binary was on `PATH`.
- `/home/steve/src/llama.cpp` was absent at lane start; a fresh upstream clone is
  appropriate.
- Disk was sufficient: about 353 GB free on `/mnt/fast-ai`.

Initial runtime decision:

1. Build upstream llama.cpp SYCL and test `UD-Q8_K_XL.gguf` first.
2. Use one process per GPU with `ONEAPI_DEVICE_SELECTOR=level_zero:N`, not
   llama.cpp multi-GPU split.
3. Compare vLLM/XPU only after the GGUF baseline exists. The likely vLLM lane is
   `google/gemma-4-26B-A4B-it --quantization int8_per_channel_weight_only`.
4. Avoid Ollama as the first optimization lane because it hides low-level B70
   flags, though it may help as a compatibility control.

External evidence recorded in the result packet:

- Unsloth provides a 27.6 GB `UD-Q8_K_XL` GGUF for this model.
- vLLM documents 26B A4B as a single-GPU BF16 model and recommends int8
  per-channel weight-only for this MoE rather than W4A16.
- vLLM Gemma 4 MoE DP has a known `--data-parallel-size > 1` crash report; this
  supports the four independent replica plan.

Setup progress:

- Fresh upstream llama.cpp cloned at `/home/steve/src/llama.cpp`, commit
  `dec5ca557`.
- `scripts/build-llama-cpp-sycl-b70.sh` completed successfully with oneAPI
  2026, `GGML_SYCL=ON`, `GGML_SYCL_F16=ON`, Level Zero support, oneDNN, and MKL.
  Binaries:
  - `/home/steve/src/llama.cpp/build-sycl-b70/bin/llama-server`
  - `/home/steve/src/llama.cpp/build-sycl-b70/bin/llama-cli`
  - `/home/steve/src/llama.cpp/build-sycl-b70/bin/llama-bench`
- llama.cpp server UI `npm install` hit a local Node-version mismatch, then
  upstream's build fell back to the prebuilt UI archive and completed. This is
  not blocking for serving.
- Q8 GGUF download started to
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/`; no local baseline run
  yet because the model file is still downloading.
