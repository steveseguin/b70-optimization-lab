# Gemma 4 26B Q8: skip identity `out_ids` negative

Date: 2026-06-28

Status: **negative / default-off / do not promote**

## Idea

For single-session Gemma 4 decode, some graph builds have
`n_outputs == n_tokens`. In that case the generated `out_ids` tensor is an
identity row mapping. The experiment added a default-off gate,
`LLAMA_GEMMA4_SKIP_IDENTITY_OUT_IDS=1`, that returns `nullptr` from
`llm_graph_context::build_inp_out_ids()` when the mapping is identity. The goal
was to avoid the host `out_ids` update and any downstream row-gather overhead.

The helper and guard were added in:

- `/home/steve/src/llama.cpp-gemma-record-repro-c926/src/llama-graph.cpp`
- `/home/steve/qwen36-results-main/scripts/run-gemma4-26b-first-baseline.sh`
- `/home/steve/qwen36-results-main/scripts/run-gemma4-26b-llamacpp-replica.sh`

The flag is recorded in run identity as
`llama_gemma4_skip_identity_out_ids`.

## Patch Shape

Conceptual source diff:

```cpp
static bool llama_graph_gemma4_skip_identity_out_ids_enabled() {
    const char * env = std::getenv("LLAMA_GEMMA4_SKIP_IDENTITY_OUT_IDS");
    return env && (std::strcmp(env, "1") == 0 || ...);
}

ggml_tensor * llm_graph_context::build_inp_out_ids() const {
    if (llama_graph_gemma4_skip_identity_out_ids_enabled() &&
        n_outputs == n_tokens && n_tokens > 0) {
        return nullptr;
    }

    // existing out_ids input construction
}
```

## Validation

All validation used the strict fresh-response gate:

- target/verifier:
  `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- draft:
  `gemma-4-26B-A4B-it-Q4_0-MTP.gguf`
- one B70 per lane, no tensor parallelism
- fixed realistic prompt suite
- every prompt once, `cached_tokens=0`
- no prompt/KV/history reuse, `--ctx-checkpoints 0`
- `n_max=3`, `n_min=2`, `p_min=0.0475`
- `UBATCH_SIZE=1024`, f16 KV, flash-attn off
- current record stack with VDR2, F16 p021 small-ncols, backend argmax IDs,
  bulk sampled IDs, direct MTP argmax unroll.

Strict 128-token screen:

- Control GPU0:
  `data/gemma4-q8-gpu0-skipoutids-control-128-20260628T205606Z/summary.json`
  median100 `97.140`.
- Skip GPU1:
  `data/gemma4-q8-gpu1-skipoutids-on-128-20260628T205606Z/summary.json`
  median100 `98.458`.
- Control GPU2:
  `data/gemma4-q8-gpu2-skipoutids-control-128-20260628T205606Z/summary.json`
  median100 `91.931`.
- Skip GPU3:
  `data/gemma4-q8-gpu3-skipoutids-on-128-20260628T205606Z/summary.json`
  median100 `96.438`.

The screen was directionally positive, so it was escalated.

Strict full512 paired confirmation:

- Control GPU0:
  `data/gemma4-q8-gpu0-skipoutids-control-full512-20260628T205810Z/summary.json`
  median100 `99.341`, p10 `87.729`, mean `98.542`, full512 `91.398`.
- Skip GPU1:
  `data/gemma4-q8-gpu1-skipoutids-on-full512-20260628T205810Z/summary.json`
  median100 `92.596`, p10 `85.843`, mean `96.518`, full512 `90.370`.
- Control GPU2:
  `data/gemma4-q8-gpu2-skipoutids-control-full512-20260628T205810Z/summary.json`
  median100 `94.400`, p10 `83.013`, mean `95.456`, full512 `90.058`.
- Skip GPU3:
  `data/gemma4-q8-gpu3-skipoutids-on-full512-20260628T205810Z/summary.json`
  median100 `96.178`, p10 `84.010`, mean `95.043`, full512 `93.560`.

## Decision

Do not promote. Full512 paired controls beat the skip lanes, so identity
`out_ids` removal is not a reliable improvement on this stack.

The `99.341` control lane is a valid strict high-side observation, but not a
new promoted record until repeated. It triggered an all-control full512 repeat.

The flag should remain default-off if the source patch is preserved. It should
not be enabled for LocalMaxxing submissions or headline reproduction.
