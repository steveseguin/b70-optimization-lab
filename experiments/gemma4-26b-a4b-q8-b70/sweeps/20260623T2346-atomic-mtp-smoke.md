# 2026-06-23 - Atomic Gemma-MTP smoke on B70

## Goal

Test whether the local Atomic Gemma-MTP implementation can leap past the
current fresh-response record (`~92.77 tok/s`) by using its advertised shared
target context, in-graph argmax, and depth-2 MTP overlap.

Source/binary:

- `/home/steve/src/atomic-llama-cpp-gemma-mtp`
- commit reported by harness: `5cf016643`
- binary: `build-sycl-b70-gemma-mtp/bin/llama-server`

Model/config:

- target: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- assistant: `gemma-4-26B-A4B-it-assistant.Q8_0.gguf`
- single B70 (`GPU_INDEX=0..3` depending on block-size screen)
- fresh-response harness; no n-gram/history headline claim

## Results

### Block size 3

Label:
`gemma4-q8-gpu0-atomicmtp-q8assist-block3-max16-smoke-filled-long-20260623T2346Z`

- canary: `64/64` pass
- fresh 512-token decode: `26.77 tok/s after TTFT`, `24.64 tok/s wall`
- MTP was active and acceptance was high on the long request:
  `339 accepted / 342 generated`
- Not competitive. The block size emits only two draft tokens per round and
  cannot approach the current validated `~92.77 tok/s` record.

### Block size 4/5/7

Canary-only screens:

- `gemma4-q8-gpu0-atomicmtp-q8assist-block4-canary-20260623T2349Z`
- `gemma4-q8-gpu1-atomicmtp-q8assist-block5-canary-20260623T2349Z`
- `gemma4-q8-gpu3-atomicmtp-q8assist-block7-canary-20260623T2349Z`

All failed immediately on the sort canary with the same corruption pattern:
spurious `<unused49>` prefix plus extra explanatory text instead of the exact
`blue, green, orange, red` answer. These are invalid for headline throughput.

### Block size 6

`gemma4-q8-gpu2-atomicmtp-q8assist-block6-canary-20260623T2349Z` timed out /
hung during the canary and required manual cleanup of the server on port
`18274`. Invalid.

## Conclusion

The local Atomic binary is not a drop-in path to the `>150 tok/s`
fresh-response target:

- the only canary-safe block size tested (`3`) is far slower than the current
  validated llama.cpp MTP stack;
- larger block sizes corrupt outputs or hang.

Keep the design idea for future porting (shared target context + overlap +
in-graph argmax are exactly the right architectural levers), but do not use the
current local Atomic run as a valid result.

