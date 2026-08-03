# Laguna wide-prefill cache and partition contract preregistration

Date: 2026-08-03 America/Toronto

Status: **preregistration plus the source change it defines; host-tested only.
No XPU, model, endpoint, benchmark, or recovery action was performed and none is
authorized.**

## Why this is preregistered rather than folded into the successor

The incumbent wide-prefill successor is gated by a sealed q12 startup contract in
`GPUModelRunner._validate_laguna_wide_prefill_qknorm_rope_config`. That contract
is the object the v3 worker attestation exists to prove. Adding conditions to it
changes what a passing attestation means, so it gets its own preregistration
instead of riding along inside an unrelated commit. This note is that record.

## The two unpinned preconditions

The 32,640-token partition `8182 + 8182 + 8182 + 8094` follows from
`token_budget = max_num_scheduled_tokens = 8182` and the `min(num_new_tokens,
token_budget)` clamp in `vllm/v1/core/sched/scheduler.py`. Two settings outside
the sealed contract can destroy that partition while every gated condition still
reports valid.

### 1. `enable_prefix_caching`

It defaults to `True` in `vllm/config/cache.py`. The long-context launcher
`serve_laguna_long_context_nvme.sh` passes `--no-enable-prefix-caching`, so the
incumbent bench path is already correct, but nothing enforces it.

With prefix caching on, a **repeated** 32,640-token prompt is served from cached
blocks. The cache hit is capped at `num_tokens - 1`, so the first scheduled chunk
becomes a small remainder rather than 8,182. That remainder is not in
`{1024, 4096, 8094, 8182}`, the per-step authentication returns zero, and the
fused path silently disables itself from the second request onward.

This is the dangerous failure mode: it is silent and it is shaped exactly like a
null result. A benchmark that loops one long prompt would measure the treatment
on iteration one and the incumbent on every iteration after, then report no
improvement. The kernel would be blamed for a scheduling artifact.

### 2. `max_num_partial_prefills`

It defaults to `1`. Above one, `vllm/config/scheduler.py` auto-sets
`long_prefill_token_threshold` to `int(max_model_len * 0.04)`, roughly 1,310
tokens at this model length. The `0 < threshold < num_new_tokens` guards in the
scheduler stop being dead code and the four-chunk partition is replaced wholesale
by ~1,310-token chunks. No registered row survives.

## Change

Both are added to the existing `invalid` dictionary, alongside the
`max_num_batched_tokens` and `max_num_scheduled_tokens` checks they belong with:

```python
"prefix_caching": bool(self.cache_config.enable_prefix_caching),
"partial_prefills": self.scheduler_config.max_num_partial_prefills != 1,
```

This is fail-closed and cannot change a numerical result. The gate is still
guarded by `VLLM_XPU_LAGUNA_WIDE_PREFILL_QKNORM_ROPE`, which remains default off,
so a worker that does not opt into the candidate is unaffected. When the
candidate is enabled, a wrong cache or partial-prefill setting now raises at
worker construction, before model load, instead of producing a quiet null.

The v3 selector contract hash is **unchanged**. That hash covers the environment
selector set in `vllm/v1/executor/laguna_selector_evidence.py`; these two are
config fields reached through `cache_config` and `scheduler_config`, exactly like
the scheduler checks already in the dictionary. No new environment variable is
introduced and no worker evidence schema changes.

## Gates for the eventual device window

Unchanged from the successor's preregistration, with one addition: the component
and endpoint legs must both record the resolved `enable_prefix_caching` and
`max_num_partial_prefills` in their run evidence, and the endpoint A/B must show
the wide-prefill path staying active across **every** repeated long row, not only
the first. A run where the fused path is active on row one and inactive
afterwards is a rejected run, not a negative result.

## Validation

Host only:

- 31 focused wide-prefill runner tests pass, three of them new: one rejecting
  prefix caching and two rejecting `max_num_partial_prefills` of 2 and 4;
- the sealed-contract acceptance test still passes with both new fields set to
  their incumbent values;
- the broader Laguna/env selection across the runner, selector-evidence,
  custom-op, and env suites was run twice, once with the change stashed. The
  failure sets are byte-identical: 12 pre-existing failures, all in M8
  breakable-graph, persistent-KV-view, and prebuilt-metadata tests that this
  change does not touch. Passing count rises `218 -> 221`, exactly the three
  new cases. No regression is introduced and none of the 12 is repaired here.

No SYCL toolchain is present, so no native code was rebuilt here; this change is
pure Python and does not affect the DSO.

## Boundary

The NVMe/device quarantine remains controlling. This authorizes no model load,
endpoint contact, XPU probe, component run, benchmark, swap change, reset,
reboot, or recovery. The candidate remains default off and unmeasured, and the
protected `125.4619731637751 tok/s` conventional short-decode record is
untouched.
