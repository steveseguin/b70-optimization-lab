# 2026-06-24T0214: Vulkan backend smoke rejected

Goal: check whether llama.cpp Vulkan on Intel B70 can beat the current SYCL
Gemma 4 26B A4B Q8 draft-MTP lane. This was worth testing because the current
single-session `>150 tok/s` target is not moving with MTP sampler knobs, and
some public B70 reports suggest Vulkan can outperform SYCL for llama.cpp on
some systems.

## Build

Source tree:

- `/home/steve/src/llama.cpp-latest-gemma`
- commit: `c926ad098`

Separate build directory:

- `/home/steve/src/llama.cpp-latest-gemma/build-vulkan-b70`

Build deps installed locally:

- `libvulkan-dev`
- `glslang-tools`
- `glslc`
- `spirv-headers`

Build command:

```bash
cmake -S . -B build-vulkan-b70 \
  -DGGML_VULKAN=ON \
  -DGGML_SYCL=OFF \
  -DLLAMA_BUILD_TESTS=OFF \
  -DLLAMA_BUILD_EXAMPLES=ON \
  -DCMAKE_BUILD_TYPE=Release
cmake --build build-vulkan-b70 --target llama-server -j 12
```

Device enumeration succeeded:

```text
Vulkan0: Intel(R) Graphics (BMG G31) (32656 MiB, 29337 MiB free)
Vulkan1: Intel(R) Graphics (BMG G31) (32656 MiB, 29369 MiB free)
Vulkan2: Intel(R) Graphics (BMG G31) (32656 MiB, 29369 MiB free)
Vulkan3: Intel(R) Graphics (BMG G31) (32656 MiB, 29369 MiB free)
```

## Smoke

Label:

- `gemma4-q8-vulkan0-mtp-n7-fastargmax-smoke-20260624T0214Z`

Run directory:

- `data/gemma4-q8-vulkan0-mtp-n7-fastargmax-smoke-20260624T0214Z/`

Server log:

- `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-vulkan0-mtp-n7-fastargmax-smoke-20260624T0214Z.server.log`

Identity:

- target: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- draft: `mtp-gemma-4-26B-A4B-it.gguf`
- devices: target `Vulkan0`, draft `Vulkan0`
- draft-MTP `n_max=7`, `n_min=2`, `p_min=0.12`
- `--no-spec-draft-backend-sampling`
- `LLAMA_MTP_DRAFT_FAST_ARGMAX=1`
- `--ctx-checkpoints 0`
- `FLASH_ATTN=off`
- `UBATCH_SIZE=512`, `BATCH_SIZE=512`, `POLL=100`
- `BENCH_PROMPT_MODE=filled-long`, `PROMPT_TOKENS=512`, `MAX_TOKENS=512`
- fresh-response hygiene: `--cache-ram 0`, `cached_tokens=0`

Result:

- canary: `32/32` pass
- fresh first request after TTFT: `42.060 tok/s`
- wall throughput: `37.026 tok/s`
- TTFT: `1.655 s`

## Decision

Rejected. Vulkan is mechanically viable but far slower than the SYCL record
lane (`92.397 tok/s` first fresh request after TTFT, 384/384 canary). Do not
spend promotion validation budget on Vulkan for this model unless upstream
Vulkan/Battlemage support changes substantially.

The result reinforces the current diagnosis: the `>150 tok/s` target will not
come from a backend swap or sampler micro-optimization. The credible path is a
structural llama.cpp change that removes host round trips from the serial Gemma4
assistant MTP draft loop, such as a fused greedy assistant unroll.
