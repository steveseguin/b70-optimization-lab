# Qwen3.6 Safe In-Place All-Reduce Screen

Date: 2026-06-10

## Context

The accepted Qwen3.6 INT8 runtime currently uses TP4, 32K context, no prefix
caching, XPU PIECEWISE graph capture, and clone-safe custom-op all-reduce.

This screen tested whether replacing provably dead out-of-place
`torch.ops.vllm.all_reduce` nodes with `torch.ops.vllm.all_reduce_inplace`
could improve single-request decode speed without changing model weights,
quantization, dtype, or context length.

## Env-Only Threshold Screen

I first tried an env-only threshold:

- `VLLM_XPU_CUSTOM_ALLREDUCE_INPLACE_MAX_NUMEL=2097152`

Runtime:

- Session: `qwen36-tp4-noprefix-inplacear-32k`
- Cache root: `/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-piecewise-graph-inplacear-32k-noprefix`
- Log: `/tmp/qwen36-quark-int8-tp4-piecewise-graph-inplacear-32k-noprefix.log`

The backend became healthy, but lowered graph inspection still showed
`torch.ops.vllm.all_reduce(...)` and did not emit `all_reduce_inplace`.
Conclusion: the existing threshold route does not affect this compiled XPU
graph path, so I stopped it without recording a benchmark.

## Source Patch

I added an opt-in local vLLM pass:

- Gate: `VLLM_XPU_EXPERIMENTAL_SAFE_INPLACE_ALLREDUCE=1`
- New pass file: `/home/steve/src/vllm/vllm/compilation/passes/utility/xpu_inplace_allreduce.py`
- Pass registration: `/home/steve/src/vllm/vllm/compilation/passes/pass_manager.py`
- Repro patch: `patches/vllm-xpu-safe-inplace-allreduce-20260610.patch`

The pass rewrites only BF16 `torch.ops.vllm.all_reduce.default` calls whose
input tensor has a single-use alias chain ending at the all-reduce. It skips
placeholders and values that remain live, so it should avoid mutating residual
hidden states that are read later.

Syntax check:

```bash
source /home/steve/.venvs/vllm-xpu/bin/activate
python -m py_compile \
  /home/steve/src/vllm/vllm/compilation/passes/utility/xpu_inplace_allreduce.py \
  /home/steve/src/vllm/vllm/compilation/passes/pass_manager.py
```

The first pass-enabled startup failed because the replacement call dropped the
positional `group_name` argument:

```text
vllm::all_reduce_inplace() is missing value for argument 'group_name'
```

I fixed the pass to forward `args=tuple(node.args)` and restarted with a fresh
compile cache.

## Candidate Runtime

Runtime:

- Session: `qwen36-tp4-noprefix-safeinplacear2-32k`
- Cache root: `/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-piecewise-graph-safeinplacear2-32k-noprefix`
- Log: `/tmp/qwen36-quark-int8-tp4-piecewise-graph-safeinplacear2-32k-noprefix.log`
- Env delta from accepted no-prefix runtime:
  `VLLM_XPU_EXPERIMENTAL_SAFE_INPLACE_ALLREDUCE=1`

Pass logs showed rewrites in the compiled partitions, including:

```text
XpuSafeInplaceAllReducePass rewrote 1 all-reduce nodes
XpuSafeInplaceAllReducePass rewrote 2 all-reduce nodes
```

Compiled-cache inspection found `36` `all_reduce_inplace` occurrences across
`20` files and `648` remaining out-of-place `torch.ops.vllm.all_reduce(...)`
occurrences across `4` files. This is a narrow rewrite, not a full collective
replacement.

## Single-Request Result

Direct-backend p512/n512 streaming, eight measured repeats:

| metric | accepted no-prefix | safe-inplace candidate | delta |
| --- | ---: | ---: | ---: |
| corrected after-first output tok/s | `98.0404` | `98.8103` | `+0.7700` |
| end-to-end output tok/s | `96.7747` | `97.5779` | `+0.8033` |
| mean client TTFT | `77.74 ms` | `75.56 ms` | `-2.18 ms` |

Artifacts:

- Accepted: `data/qwen36-quark-int8-tp4-noprefix-graph32k-single-confirm-20260610.json`
- Candidate: `data/qwen36-quark-int8-tp4-noprefix-safeinplacear2-graph32k-single-20260610.json`

## Quality

Matched frontdoor quality passed with full baseline parity:

- exact canaries: pass
- JSON field semantics: pass
- repeat stability: pass
- 8K-class long-context needle recall: pass
- baseline match: pass

Artifact:

- `data/qwen36-quark-int8-tp4-noprefix-safeinplacear2-frontdoor-quality-20260610.json`

## Aggregate Throughput

Frontdoor p512/n256 concurrency sweep:

| c | accepted wall tok/s | candidate wall tok/s | delta wall | accepted from-first tok/s | candidate from-first tok/s | delta from-first |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `95.94` | `96.65` | `+0.71` | `99.02` | `99.68` | `+0.66` |
| 2 | `170.19` | `173.76` | `+3.57` | `181.10` | `178.34` | `-2.76` |
| 4 | `307.85` | `315.00` | `+7.15` | `316.24` | `322.77` | `+6.53` |
| 8 | `553.27` | `526.71` | `-26.56` | `566.10` | `538.23` | `-27.87` |
| 16 | `851.63` | `915.93` | `+64.30` | `868.43` | `935.83` | `+67.40` |
| 32 | `1397.95` | `1385.72` | `-12.23` | `1419.06` | `1412.48` | `-6.57` |
| 48 | `1700.89` | `1534.37` | `-166.51` | `1727.50` | `1550.78` | `-176.72` |

Artifacts:

- Accepted: `data/qwen36-quark-int8-tp4-noprefix-graph32k-concurrency-20260610.json`
- Candidate: `data/qwen36-quark-int8-tp4-noprefix-safeinplacear2-graph32k-concurrency-20260610.json`

## Capped Rewrite Follow-Up

After the c48 regression, I added a cap to the diagnostic pass:

- `VLLM_XPU_SAFE_INPLACE_ALLREDUCE_MAX_REWRITES_PER_GRAPH=1`

Runtime:

- Session: `qwen36-tp4-noprefix-safeinplacearmax1-32k`
- Cache root: `/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-piecewise-graph-safeinplacearmax1-32k-noprefix`
- Log: `/tmp/qwen36-quark-int8-tp4-piecewise-graph-safeinplacearmax1-32k-noprefix.log`
- Env delta from the uncapped candidate:
  `VLLM_XPU_SAFE_INPLACE_ALLREDUCE_MAX_REWRITES_PER_GRAPH=1`

The cap worked as intended; pass logs showed one rewrite and one skipped live
candidate in graph partitions that previously rewrote two.

Direct-backend p512/n512 streaming, eight measured repeats:

| metric | accepted no-prefix | uncapped safe-inplace | max1 capped |
| --- | ---: | ---: | ---: |
| corrected after-first output tok/s | `98.0404` | `98.8103` | `97.9948` |
| end-to-end output tok/s | `96.7747` | `97.5779` | `96.7871` |
| mean client TTFT | `77.74 ms` | `75.56 ms` | `75.40 ms` |

Artifact:

- `data/qwen36-quark-int8-tp4-noprefix-safeinplacearmax1-graph32k-single-20260610.json`

Decision: reject the capped variant. It failed the first speed gate by losing
the single-request gain, so I did not spend time on quality or aggregate sweeps.

## Decision

Do not promote this as the production default. It is quality-safe and improves
single-request speed by about `0.79%`, but the c48 aggregate regression is too
large for a general runtime profile.

Keep the patch as an opt-in diagnostic and a direction for more precise
collective-boundary work. The accepted runtime remains the no-prefix TP4 32K
profile without `VLLM_XPU_EXPERIMENTAL_SAFE_INPLACE_ALLREDUCE`.
