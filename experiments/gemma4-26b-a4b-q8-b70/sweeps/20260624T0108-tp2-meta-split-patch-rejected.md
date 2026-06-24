# 2026-06-24T0108: TP=2 meta/split patch rejected for Gemma4 shared KV

Goal: unblock a >150 tok/s path for Gemma 4 26B A4B Q8 by making TP=2 /
cross-GPU llama.cpp startup work on two B70s. The current single-GPU MTP n=7
fresh record is still only ~92-94 tok/s; >150 likely needs either true
multi-GPU speedup or a non-serial draft path.

## Patch Tested

Patch snapshot:

- `patches/gemma4-llamacpp-tp2-meta-split-experiment-20260624.patch`

Source tree tested:

- `/home/steve/src/llama.cpp-latest-gemma`
- base reported by harness: `c926ad098`
- build: `build-sycl-b70-aot-bmg-g31/bin/llama-server`

Patch source:

- inspired by llama.cpp issue `#21788`, "Allow SPLIT_MODE_TENSOR with KV cache
  quantization": <https://github.com/ggml-org/llama.cpp/issues/21788>
- touched:
  - `ggml/src/ggml-backend-meta.cpp`
  - `src/llama-graph.cpp`
  - `src/llama-kv-cache.cpp`

The patch compiled successfully after a full SYCL BMG-G31 AOT relink.

## Runs

Tensor split, FA on:

- label: `gemma4-q8-tp2-12-tensorsplit-metaexperiment-faon-fitoff-mtpn7-smoke-20260624T005759Z`
- data dir:
  `data/gemma4-q8-tp2-12-tensorsplit-metaexperiment-faon-fitoff-mtpn7-smoke-20260624T005759Z/`
- server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-tp2-12-tensorsplit-metaexperiment-faon-fitoff-mtpn7-smoke-20260624T005759Z.server.log`
- identity:
  - `ONEAPI_DEVICE_SELECTOR=level_zero:1,2`
  - `LLAMA_DEVICES=SYCL0,SYCL1`
  - `LLAMA_SPLIT_MODE=tensor`
  - `LLAMA_TENSOR_SPLIT=1,1`
  - `FLASH_ATTN=on`
  - `CACHE_TYPE_K=f16`, `CACHE_TYPE_V=f16`
  - `MTP_EXTRA_ARGS='--ctx-checkpoints 0 --fit off'`

Outcome:

- failed before readiness
- same abort as before the patch:
  `pre-allocated tensor (cache_k_l28) in a buffer (Meta()) that cannot run the operation (NONE)`
- stack top: `ggml_backend_sched_backend_id_from_cur` during
  `llama_context::graph_reserve` / `sched_reserve`

Tensor split, FA off control:

- label: `gemma4-q8-tp2-12-tensorsplit-metaexperiment-faoff-fitoff-mtpn7-smoke-20260624T010030Z`
- data dir:
  `data/gemma4-q8-tp2-12-tensorsplit-metaexperiment-faoff-fitoff-mtpn7-smoke-20260624T010030Z/`
- outcome: invalid control; llama.cpp rejects it before graph reservation:
  `SPLIT_MODE_TENSOR requires flash_attn to be enabled`

Row split control:

- label: `gemma4-q8-tp2-12-rowsplit-metaexperiment-fitoff-mtpn7-smoke-20260624T010149Z`
- data dir:
  `data/gemma4-q8-tp2-12-rowsplit-metaexperiment-fitoff-mtpn7-smoke-20260624T010149Z/`
- identity:
  - `ONEAPI_DEVICE_SELECTOR=level_zero:1,2`
  - `LLAMA_DEVICES=SYCL0,SYCL1`
  - `LLAMA_SPLIT_MODE=row`
  - `LLAMA_TENSOR_SPLIT=1,1`
  - `FLASH_ATTN=off`
  - `CACHE_TYPE_K=f16`, `CACHE_TYPE_V=f16`
  - `MTP_EXTRA_ARGS='--ctx-checkpoints 0 --fit off'`

Outcome:

- failed before readiness with a segfault during model/server initialization
- same class as the earlier row-split startup failure; no throughput or quality
  data produced

Plain target tensor split control (no MTP / no draft assistant):

- label: `gemma4-q8-tp2-12-tensorsplit-plain-target-metaexperiment-smoke-20260624T010342Z`
- data dir:
  `data/gemma4-q8-tp2-12-tensorsplit-plain-target-metaexperiment-smoke-20260624T010342Z/`
- identity:
  - `ONEAPI_DEVICE_SELECTOR=level_zero:1,2`
  - `LLAMA_DEVICES=SYCL0,SYCL1`
  - `LLAMA_SPLIT_MODE=tensor`
  - `LLAMA_TENSOR_SPLIT=1,1`
  - `FLASH_ATTN=on`
  - `EXTRA_LLAMA_ARGS='--parallel 1 --cache-ram 0 --fit off'`

Outcome:

- reached readiness
- tiny canary: `4/4` pass
- tiny generation: one 16-token request completed
- decode was slow (`31.77 tok/s after TTFT` on the tiny request), but this was
  only a startup/isolation control, not a performance claim

## Interpretation

This patch is rejected for our Gemma4 26B Q8 TP=2 goal.

The issue `#21788` patch class targets attention-rotation / KV-quantization split
inference. Our run already uses F16 KV (`-ctk f16 -ctv f16`) and still fails,
so the blocker is not KV quantization compatibility. The failure is specific to
Gemma4 assistant/MTP shared-KV context plus scheduler placement:

- the plain target Gemma4 TP=2 tensor-split context can start;
- the MTP/draft assistant context shares target KV and fails during startup;
- assistant layers 0-3 share target KV with layers 28/29;
- during `sched_reserve`, llama.cpp builds reservation graphs with meta/no-alloc
  tensors;
- the shared layer structure points at `cache_k_l28` / `cache_v_l28`, and the
  scheduler treats that preallocated Meta buffer as a tensor that must run an op;
- `ggml_backend_sched_backend_id_from_cur` aborts because a `Meta()` buffer
  cannot run `NONE`.

The patch was reverted from the live llama.cpp source after testing. Keep the
patch file and these result directories as a failed experiment so we do not
retry the same subsystem patch for this different shared-KV failure.

## Next Actions

Useful TP=2 work now needs to target shared-KV/scheduler placement directly,
not attention-rotation reshape inference. Candidate directions:

1. Teach `llama_kv_cache` shared layers to preserve/use the source tensor's real
   backend placement during no-alloc reservation, instead of copying a layer
   whose tensors are backed by Meta in the reservation context.
2. Adjust the scheduler's handling of preallocated shared KV tensors during
   split-only reservation so `GGML_OP_NONE` data tensors from Meta are treated as
   leaf/storage tensors, not runnable nodes.
3. Rebuild with a narrow `GGML_OP_NONE` storage-leaf scheduler patch and rerun
   the MTP tensor-split smoke. The patch should prove itself by moving past the
   `cache_k_l28 Meta()/NONE` abort; any new failure should be treated as the next
   concrete blocker, not as a benchmark result.

## Follow-up: storage-leaf scheduler patch was not sufficient

Patch snapshot:

- `patches/gemma4-llamacpp-tp2-sharedkv-none-leaf-scheduler-20260624.patch`

Patch idea:

- in `ggml_backend_sched_backend_from_buffer`, treat `GGML_OP_NONE` as a storage
  leaf so scheduler placement does not require `supports_op(NONE)` for a
  preallocated shared-KV tensor.

Run:

- label: `gemma4-q8-tp2-12-tensorsplit-schedulerleaf-faon-fitoff-mtpn7-smoke-20260624T011353Z`
- data dir:
  `data/gemma4-q8-tp2-12-tensorsplit-schedulerleaf-faon-fitoff-mtpn7-smoke-20260624T011353Z/`
- server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-tp2-12-tensorsplit-schedulerleaf-faon-fitoff-mtpn7-smoke-20260624T011353Z.server.log`
- identity matched the earlier tensor-split MTP smoke, with target on
  `LLAMA_DEVICES=SYCL0,SYCL1`, `LLAMA_SPLIT_MODE=tensor`,
  `LLAMA_TENSOR_SPLIT=1,1`, `FLASH_ATTN=on`, and the MTP draft on the wrapper
  default `MTP_DRAFT_DEVICE=SYCL0`.

Outcome:

- failed before readiness with the same abort:
  `pre-allocated tensor (cache_k_l28) in a buffer (Meta()) that cannot run the operation (NONE)`
- this proves `supports_op(NONE)` was not the limiting check; no scheduler
  backend in the draft context claimed the borrowed target `Meta()` buffer type.

Revised interpretation:

- the target TP=2 tensor-split context can start by itself;
- the failing path is the assistant/MTP shared-KV context borrowing target KV;
- the harness was also placing the draft on only `SYCL0` while the target was
  tensor-split across `SYCL0,SYCL1`, which is a plausible cause of the
  borrowed-Meta-buffer placement mismatch.

Next concrete bisection:

- fix the MTP wrapper so comma-separated draft device lists are passed literally
  (not shell-escaped as `SYCL0\\,SYCL1`);
- test `MTP_DRAFT_DEVICE=SYCL0,SYCL1` with the same TP=2 target placement before
  adding deeper scheduler or shared-KV code.

## Follow-up: matching draft devices moves past startup but is not viable yet

Harness fix:

- `scripts/run-gemma4-26b-mtp-candidate.sh` now treats a positional argument as
  `LABEL` and serializes `EXTRA_LLAMA_ARGS` without `%q`, because the downstream
  replica harness does a simple whitespace split. With `%q`, comma-separated
  device lists were passed literally as `SYCL0\,SYCL1`, and llama.cpp rejected
  `--spec-draft-device`.

Matched-draft runs:

- `data/gemma4-q8-tp2-12-tensorsplit-draftsplit-sps0-nocache-schedulerleaf-faon-fitoff-mtpn7-smoke-20260623T212018Z/`
- `data/gemma4-q8-tp2-12-tensorsplit-draftsplit-sps0-nocache-nobs-schedulerleaf-faon-fitoff-mtpn7-smoke-20260623T212155Z/`

Identity:

- target: `ONEAPI_DEVICE_SELECTOR=level_zero:1,2`,
  `LLAMA_DEVICES=SYCL0,SYCL1`, `LLAMA_SPLIT_MODE=tensor`,
  `LLAMA_TENSOR_SPLIT=1,1`, `FLASH_ATTN=on`
- draft: `MTP_DRAFT_DEVICE=SYCL0,SYCL1`, `--spec-draft-ngl all`
- fresh-response hygiene: `--cache-ram 0`, `--ctx-checkpoints 0`,
  `--slot-prompt-similarity 0`, `--no-cache-prompt`
- second run also used `MTP_BACKEND_SAMPLING=0` so fast argmax was active.

Outcome:

- both matched-draft runs reached readiness and completed the first canary
  request, proving the earlier startup-only `Meta()/NONE` abort was at least
  partly a target/draft placement mismatch;
- both then aborted on the second fresh request in
  `ggml/src/ggml-sycl/fattn.cpp:215`:
  `Not support Flash-Attention`, inside `common_speculative_impl_draft_mtp::draft`;
- disabling slot prompt similarity and prompt-cache reuse did not change the
  crash, so it is not a warmed-prefix/cache artifact;
- disabling backend sampling made `draft_fast_argmax=1`, but still crashed.

Performance signal:

- the first completed request was slow: around **48 tok/s** on the short canary
  decode, with draft acceptance `9/14` and mean acceptance length `5.50`;
- this is not close to the >150 tok/s target and is not a headline result
  because the server crashes on subsequent fresh requests.

Conclusion:

- TP=2 tensor split is partially unblocked (startup + one request), but it is
  not currently a promising route. The next real TP=2 fix would need to address
  SYCL flash-attention support/state for repeated shared-KV MTP requests, and
  then still prove a large throughput gain. For now, continue optimization on
  single-GPU replicas where the best valid fresh-response result is ~92-94 tok/s
  and the hardware can run four independent sweeps at once.
