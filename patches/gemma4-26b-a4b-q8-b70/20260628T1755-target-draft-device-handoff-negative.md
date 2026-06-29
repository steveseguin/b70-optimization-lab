# Target-to-draft device `h_nextn` handoff negative

Date: 2026-06-28

Model/config lane:

- target: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- draft: `MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf`
- hardware: single Intel B70 GPU lane
- strict gate: fixed realistic suite, one cold response per prompt,
  `cached_tokens=0`, no history/warmed/reuse acceleration
- baseline knobs: VDR2/Q8 reorder, bulk sampled verifier IDs, `n_max=3`,
  `n_min=2`, `p_min=0.0475`, `UBATCH_SIZE=1024`

## Idea

Avoid the target `h_nextn` row host staging for the first draft step. The
existing `LLAMA_MTP_DRAFT_DEVICE_H_HANDOFF` only copies draft `h_nextn` to the
next draft input within the same draft context. This experiment added a
separate default-off `LLAMA_MTP_TARGET_DRAFT_DEVICE_H_HANDOFF=1` path to copy
the target context `t_h_nextn[row]` directly into the draft context
`t_inp_embd[0]`.

Touched files during the experiment:

- `/home/steve/src/llama.cpp-gemma-record-repro-c926/src/llama-context.h`
- `/home/steve/src/llama.cpp-gemma-record-repro-c926/src/llama-context.cpp`
- `/home/steve/src/llama.cpp-gemma-record-repro-c926/src/llama-ext.h`
- `/home/steve/src/llama.cpp-gemma-record-repro-c926/common/speculative.cpp`
- `scripts/run-gemma4-26b-first-baseline.sh`
- `scripts/run-gemma4-26b-llamacpp-replica.sh`

## Implementation notes

The first implementation used `ggml_view_1d()` row views and called
`ggml_backend_tensor_copy(src_row, dst_row)`. That crashed immediately:

```text
GGML_ASSERT(buffer) failed
```

Root cause: `ggml_view_1d()` leaves the temporary view's `buffer` null and
stores the real allocation on `view_src`. `ggml_backend_tensor_copy()` checks
`src->buffer` directly before it reaches the generic copy helper. A second
attempt initialized both row views with exported `ggml_backend_view_init()`
before the copy. That fixed the crash and produced valid output.

## Results

Paired strict128 screen:

| lane | median tok/s 1-100 | p10 | mean | full128 median | validity | summary |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| control | `99.469` | `92.506` | `99.758` | `99.049` | pass/cached0/canary | `data/gemma4-q8-gpu0-targethandoff-control-strict128-20260628T1743Z/summary.json` |
| `LLAMA_MTP_TARGET_DRAFT_DEVICE_H_HANDOFF=1` + `ggml_backend_view_init()` | `93.456` | `88.244` | `96.287` | `94.803` | pass/cached0/canary | `data/gemma4-q8-gpu1-targethandoff-viewinit-strict128-20260628T1755Z/summary.json` |

Decision: **closed negative**.

The safe row-view device copy is slower than the current host-staged path in
this decode loop. It likely synchronizes/waits in the SYCL backend copy path,
so it adds more overhead than the host copy it replaces. Do not promote this
hook for headline work.

## Follow-up implication

Cross-context `h_nextn` handoff is still conceptually attractive, but it needs a
graph-integrated copy/input aliasing approach, not an eager
`ggml_backend_tensor_copy()` between contexts. For the >100 reliable goal, spend
near-term effort on verifier LM-head reduction or hardening already observed
near-100 lanes rather than this copy path.
