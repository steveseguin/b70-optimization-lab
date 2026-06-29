# Gemma 4 26B Q8: sampler-clone skip negative

Date: 2026-06-28

Status: **negative / reverted**

## Idea

The server speculative accept path cloned sampler state before every verifier
accept step:

```cpp
common_sampler_ptr smpl_save(common_sampler_clone(slot.smpl.get()));
```

`finish_speculative_accept()` only consumes that clone when checkpoint restore
is required. The strict Gemma lane runs with `--ctx-checkpoints 0` and RS
rollback support, so most steps should be able to remove rejected draft tokens
directly. The patch skipped the clone unless checkpoint restore could actually
be needed.

## Patch Shape

Added a conservative helper in `tools/server/server-context.cpp`:

```cpp
bool speculative_accept_may_need_sampler_restore(size_t n_draft) const {
    return ctx_tgt_seq_rm_type == COMMON_CONTEXT_SEQ_RM_TYPE_FULL ||
        (ctx_tgt_seq_rm_type == COMMON_CONTEXT_SEQ_RM_TYPE_RS &&
         n_draft > (size_t) llama_n_rs_seq(ctx_tgt));
}
```

Then both speculative accept clone sites used:

```cpp
common_sampler_ptr smpl_save(nullptr);
if (speculative_accept_may_need_sampler_restore(n_draft)) {
    smpl_save.reset(common_sampler_clone(slot.smpl.get()));
}
```

The helper used `n_draft` as a conservative rollback upper bound so it would not
skip the clone when a later partial-accept path could require checkpoint
restore.

## Validation

Run:
`data/gemma4-q8-gpu1-cloneskip-screen128-20260628T184620Z/summary.json`

Identity:

- Target/verifier: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- Draft: `gemma-4-26B-A4B-it-Q4_0-MTP.gguf`
- GPU: one B70, `ONEAPI_DEVICE_SELECTOR=level_zero:1`
- `n_max=3`, `n_min=2`, `p_min=0.0475`
- `UBATCH=1024`, `ctx=8192`
- `LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1`
- `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`
- `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`
- `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1`
- `--ctx-checkpoints 0`
- Fixed realistic suite, each prompt once, `cached_tokens=0`

Result:

- Canary: pass, 32 repeats
- Fresh-response validity: pass, all `cached_tokens=0`
- Median 1-100 after TTFT: `97.7066 tok/s`
- p10: `85.7153 tok/s`
- Mean: `96.4585 tok/s`
- Full128 after TTFT median: `93.6701 tok/s`

Current standing strict record:
`98.3405 tok/s` median 1-100 after TTFT, full512 confirmation.

## Decision

Do not promote. The patch was reverted after the screen. It is exact in shape,
but it does not move the strict distribution above the current record and is not
a reliable route to `>100 tok/s`.

This also reinforced a process point: even server-side changes can trigger a
long BMG AOT relink in the dirty build tree. Future source work should focus on
larger-headroom verifier row reduction rather than small host-side cleanup
unless profiling proves the cleanup is material.
