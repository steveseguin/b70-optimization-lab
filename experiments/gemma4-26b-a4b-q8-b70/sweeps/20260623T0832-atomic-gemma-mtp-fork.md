# Atomic Gemma-MTP Fork Smoke

Date: 2026-06-23
Owner/agent: Codex
GPU / port: GPU0 / `18260`

## Hypothesis

Upstream llama.cpp draft-MTP has plateaued at `48.35 tok/s` for the valid Q8
single-B70 lane. The AtomicChat fork advertises a Gemma 4 MTP path where the
assistant is loaded into the target context, shares target KV, uses in-graph
argmax, and avoids a second draft context/KV. That structural change could
remove enough upstream MTP overhead to break the current record.

## Artifacts

- main model:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- AtomicChat Q8 assistant:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-assistant.Q8_0.gguf`
- assistant metadata:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-assistant.Q8_0.gguf.metadata.json`
- local fork worktree:
  `/home/steve/src/atomic-llama-cpp-gemma-mtp`
- tested branch / commit:
  `origin/feature/gemma-mtp`, `5cf0166431fba1f7c8d4631b430848e34695c255`
- build:
  `/home/steve/src/atomic-llama-cpp-gemma-mtp/build-sycl-b70-gemma-mtp/bin/llama-server`
- local crash fix patch:
  `patches/atomic-gemma-mtp-scheduler-callback-fix-20260623.patch`

The default Atomic branch `feature/turboquant-kv-cache` at
`d86eb0b8cd22507f05ba09975dcc979331ab62ba` built successfully in
`/home/steve/src/atomic-llama-cpp-turboquant/build-sycl-l0-server/bin/llama-server`,
but its CLI exposes upstream-style `--spec-type draft-mtp` rather than the
documented Gemma-specific `--mtp-head` / `--spec-type mtp` /
`--draft-block-size` path. Its Python verifier also has an internal GGUF enum
mismatch. The `feature/gemma-mtp` worktree was the correct target for this
experiment.

## Results

| Label | Config | Canary | Tok/s after TTFT | Decision |
| --- | --- | ---: | ---: | --- |
| `gemma4-q8-gpu0-atomic-mtp-block3max8-f16kv-smoke-20260623T0832` | unpatched MTP, `GGML_SYCL_DISABLE_OPT=0`, FA off | crash | n/a | segfault on first chat request |
| `gemma4-q8-gpu0-atomic-mtp-block3max8-faon-f16kv-smoke-20260623T0834` | unpatched MTP, `GGML_SYCL_DISABLE_OPT=0`, FA on | crash | n/a | same segfault |
| `gemma4-q8-gpu0-atomic-nospec-faoff-smoke-20260623T0835` | no-spec, `GGML_SYCL_DISABLE_OPT=0` | failed 2nd row | n/a | corrupt output: repeated `<unused32>` |
| `gemma4-q8-gpu0-atomic-nospec-opt1-faoff-smoke-20260623T0836` | no-spec, `GGML_SYCL_DISABLE_OPT=1` | 16/16 | `24.70` | quality-safe but far slower than upstream |
| `gemma4-q8-gpu0-atomic-mtp-opt1-block3max8-faon-smoke-20260623T0837` | unpatched MTP, `GGML_SYCL_DISABLE_OPT=1`, FA on | crash | n/a | same segfault, so crash is independent of optimized SYCL |
| `gemma4-q8-gpu0-atomic-mtp-patched-opt1-block3max8-faon-smoke-20260623T0844` | patched MTP, `GGML_SYCL_DISABLE_OPT=1`, FA on, block 3 / max 8 | 16/16 | `18.13` | crash fixed, but MTP is slower than no-spec |
| `gemma4-q8-gpu0-atomic-mtp-patched-opt0-block3max8-faon-smoke-20260623T0846` | patched MTP, `GGML_SYCL_DISABLE_OPT=0`, FA on | hung | n/a | stuck in first canary prompt processing |

## Crash Diagnosis And Patch

GDB backtrace for the unpatched `feature/gemma-mtp` MTP crash:

```text
llama_model::n_gpu_layers() const
std::_Function_handler<... llama_context::graph_get_cb() ...>
llm_graph_context::build_pooling(...)
llama_model::build_graph(...)
llama_context::ensure_sched_mtp()
llama_context::decode_mtp_async(...)
common_speculative_state_mtp::draft(...)
server_context_impl::update_slots()
```

Root cause: `graph_params_mtp()` reused the target scheduler and target
`graph_get_cb()`. The target callback calls `model.n_gpu_layers()` and
`model.dev_layer(il)` while building an assistant/MTP graph. That can dereference
invalid target-layer assumptions during MTP graph reserve/build. The patch:

- makes MTP graph params use `sched_mtp.get()`;
- adds an MTP-only callback that only names tensors;
- applies that MTP callback during reserve and real MTP graph builds.

The patch fixed the segfault: the patched `OPT=1` MTP smoke completed 16/16
canary rows.

## Decision

Not a record path today.

The useful outcome is the crash fix and the finding that Atomic's Gemma-MTP path
is not yet quality/performance viable for this B70 Q8 lane:

- `GGML_SYCL_DISABLE_OPT=0` is unusable in this fork: no-spec corrupts and MTP
  hangs after the crash fix.
- `GGML_SYCL_DISABLE_OPT=1` is quality-safe but slow (`24.70 tok/s` no-spec),
  and patched MTP is slower still (`18.13 tok/s`).

Keep the patch and notes for a future revisit if the fork's optimized SYCL
corruption is fixed. For current record-seeking, return to upstream llama.cpp
AOT n=3 or try vLLM int8-per-channel as a separate lane.
