# Qwen3.6 27B MTP GGUF Q4 on B70

This lane is an alternate INT4/Q4 path for Qwen3.6 27B, separate from the
Intel AutoRound vLLM result packet.

## Identity

- Model repo: `unsloth/Qwen3.6-27B-MTP-GGUF`
- Target file: `Qwen3.6-27B-UD-Q4_K_XL.gguf`
- Runtime: llama.cpp/SYCL on Intel Arc Pro B70
- Local model path:
  `/mnt/usb-models/models/qwen36-27b-mtp-gguf/Qwen3.6-27B-UD-Q4_K_XL.gguf`
- Local source: `/home/steve/src/llama.cpp`
- Build dir: `/home/steve/src/llama.cpp/build-sycl-b70-qwen36-mtp`
- Fallback JIT build dir:
  `/home/steve/src/llama.cpp/build-sycl-b70-qwen36-mtp-jit`
- Launcher: `../../scripts/serve-qwen36-27b-mtp-gguf-llamacpp.sh`

This is a different checkpoint, quantization format, and runtime from
`Intel/Qwen3.6-27B-int4-AutoRound`. Compare it as a separate Q4/INT4 lane.

## Policy

Diagnostic sweeps may use synthetic prompts, but headline results require the
same fresh-response gate:

- fixed realistic prompt suite;
- each prompt once as a cold first response;
- no prompt/KV/cache/checkpoint/history/repeated-output acceleration;
- target model and quantization unchanged;
- MTP/speculation allowed only when accepted tokens are verified by the target;
- primary metric is median generated-token throughput for tokens 1-100 after
  TTFT across the suite.

If llama.cpp does not report `cached_tokens`, record that explicitly and use
server settings that disable context checkpoints and prompt caching. Do not
submit or promote any row that depends on warmed repeated prompts or n-gram
history.

## Initial Plan

1. Build clean upstream llama.cpp with SYCL for B70.
2. Download `UD-Q4_K_XL` to the USB model drive.
3. Start one GPU, one model copy, `draft-mtp` enabled with `n_max=3`.
4. Run OpenAI smoke in chat mode with thinking disabled.
5. Run the Qwen realistic suite once for a first strict baseline.
6. Compare no-spec versus MTP and then sweep `MTP_N_MAX`, `MTP_N_MIN`,
   `MTP_P_MIN`, graph on/off, ubatch, and flash attention only after smoke
   quality passes.

## Current State

- 2026-07-03: upstream llama.cpp fast-forwarded from `dec5ca557` to
  `fdb1db877` in the clean `/home/steve/src/llama.cpp` tree.
- 2026-07-03: SYCL build started at
  `/home/steve/src/llama.cpp/build-sycl-b70-qwen36-mtp` with
  `GGML_SYCL_DEVICE_ARCH=bmg-g31`.
- 2026-07-03: AOT and JIT SYCL builds completed. The AOT server reports
  llama.cpp `9860 (fdb1db877)` when `/opt/intel/oneapi/setvars.sh` is sourced.
  A raw fresh shell fails to run it with `libsvml.so` missing; use the launcher
  or source oneAPI before invoking the binary.
- 2026-07-03: Hugging Face download started for
  `unsloth/Qwen3.6-27B-MTP-GGUF:Qwen3.6-27B-UD-Q4_K_XL.gguf` into
  `/mnt/usb-models/models/qwen36-27b-mtp-gguf`. File size from Hugging Face
  metadata is `17,909,097,600` bytes.
- 2026-07-03: Download completed, one-slot llama.cpp server smoke passed, and
  the first strict fresh-response sweep closed. Best GGUF row is
  `30.679 tok/s` median tokens 1-100 after TTFT (`draft-mtp n_max=3`), while
  no-spec is `23.567 tok/s`. MTP helps but this lane is far behind the
  separate Intel AutoRound vLLM/XPU lane at `53.522 tok/s`. Config-only GGUF
  sweeps of MTP4/5, `n_min/p_min`, ubatch, VMM, FlashAttention, immediate
  command lists, and Q8 KV did not produce a win. See
  `../../results/qwen36-27b-mtp-gguf-q4-b70/initial-realistic-sweep-20260703.json`.
- 2026-07-05: refreshed the lane after fixing harness defaults for strict
  cache-off B70 runs. The server wrappers now default to
  `ONEAPI_DEVICE_SELECTOR=level_zero:*` and `ZE_AFFINITY_MASK=$GPU_INDEX`;
  Qwen GGUF bench wrappers default to `{"cache_prompt":false}`. The current
  MTP3 refresh reached `30.812 tok/s`, and a four-GPU depth screen produced
  no-spec `23.675`, MTP3 `29.514`, MTP4 `28.599`, and MTP5 `24.904 tok/s`.
  Every row passed the fixed realistic gate with `cached_tokens=0`, but the
  lane remains far below the vLLM AutoRound `65.276 tok/s` row. See
  `notes/2026-07-05-cacheoff-selector-refresh.md`.
- 2026-07-05: fixed a Bash JSON-default bug in the GGUF benchmark wrapper and
  screened deeper MTP with `p_min` across four B70s. Best row was MTP7 with
  `n_min=1`, `p_min=0.65` at `31.480 tok/s`; all rows were strict
  fresh/cached-zero, but none changed the conclusion. See
  `notes/2026-07-05-pmin-screen-and-harness-fix.md`.

## Research Notes

- Public Unsloth model metadata says the MTP GGUF is intended for llama.cpp and
  documents `llama-server -hf unsloth/Qwen3.6-27B-MTP-GGUF:UD-Q4_K_XL`.
- Current llama.cpp docs list the speculative type as `draft-mtp`; use
  `--spec-type draft-mtp`, not n-gram/history methods, for fresh-response
  headline candidates.
- Early bring-up should use one B70 per process, not tensor parallel, to avoid
  PCIe/collective overhead and to allow four independent research replicas.
- For this GGUF, `n_max=3` remains the useful default depth. Deeper p-min
  screens reached only `31.48 tok/s` at best and remain far behind vLLM.
