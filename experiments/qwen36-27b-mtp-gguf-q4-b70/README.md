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

## Research Notes

- Public Unsloth model metadata says the MTP GGUF is intended for llama.cpp and
  documents `llama-server -hf unsloth/Qwen3.6-27B-MTP-GGUF:UD-Q4_K_XL`.
- Current llama.cpp docs list the speculative type as `draft-mtp`; use
  `--spec-type draft-mtp`, not n-gram/history methods, for fresh-response
  headline candidates.
- Early bring-up should use one B70 per process, not tensor parallel, to avoid
  PCIe/collective overhead and to allow four independent research replicas.
