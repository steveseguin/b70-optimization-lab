# Qwen3.6 GDN View-Alias Quant Reuse Rejected

Date: 2026-06-10

## Context

Current accepted runtime:

- Model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`
- Runtime: vLLM XPU, TP4, 32K, Quark W8A8 INT8, BF16 activations
- Prefix cache: disabled
- XPU graph: PIECEWISE
- Accepted GDN setting: `VLLM_XPU_GDN_REUSE_QKVZ_BA_QUANT=clone`
- Accepted `_xpu_C` hash:
  `d2c6cc8d1cc92c3671a3a9357bed6c5783bdbcf505ee663d16f2e42f1e46ce8c`

The unguarded shared-quant path was previously faster but quality-unstable.
The clone-guarded path is quality-stable but pays for four tensor clones per GDN
projection pair. This candidate tested a lower-overhead barrier:

```python
x_q_qkvz = x_q.view_as(x_q)
x_s_qkvz = x_s.view_as(x_s)
x_q_ba = x_q.view_as(x_q)
x_s_ba = x_s.view_as(x_s)
```

The hypothesis was that the instability might come from graph/custom-op argument
identity rather than shared storage. If so, distinct tensor views could be
quality-safe without copying data.

## Candidate

Patch artifact:

- `patches/vllm-qwen36-gdn-reuseqkvzbaquant-view-rejected-20260610.patch`

Runtime:

- tmux: `qwen36-tp4-gdn-reusequant-view-32k`
- cache root:
  `/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-piecewise-graph-gdn-reuseqkvzbaquant-view-32k-noprefix`
- env: `VLLM_XPU_GDN_REUSE_QKVZ_BA_QUANT=view`

Startup telemetry:

- checkpoint size: `34.15 GiB`
- model loading memory: `8.58 GiB`
- torch.compile: `54.92 s`
- graph capture completed and `/health` passed

## Speed Gate

Artifact:

- `data/qwen36-quark-int8-tp4-noprefix-gdn-reuseqkvzbaquant-view-single-r8-20260610.json`

Result:

| metric | view alias | accepted control family |
| --- | ---: | ---: |
| corrected after-first output tok/s | `99.1477` | `~99.3-99.8` |
| e2e output tok/s | `97.3187` | `~98.0-98.6` |
| mean client TTFT | `76.21 ms` | `~74-79 ms` |

Representative accepted controls:

- `data/qwen36-quark-int8-tp4-noprefix-gdn-reuseqkvzbaquant-clone-envclean-single-r8-20260610.json`
  - corrected after-first: `99.3181 tok/s`
  - e2e: `97.9820 tok/s`
  - TTFT: `79.45 ms`
- `data/qwen36-quark-int8-tp4-noprefix-restore-after-xpushared-reject-r4-20260610.json`
  - corrected after-first: `99.7816 tok/s`
  - e2e: `98.5507 tok/s`
  - TTFT: `74.11 ms`

## Decision

Rejected at the endpoint speed gate.

The view-alias barrier did not beat the accepted clone-mode runtime. It improved
over the scratchpad-ring shared-quant candidate's TTFT, but it still landed
below the accepted speed controls. Because speed failed first, the full quality
suite was not run.

This suggests that a no-copy tensor-wrapper barrier is not enough to make GDN
shared quant reuse worth keeping. If the unguarded quality issue is aliasing,
the relevant alias likely involves shared storage/lifetime rather than only the
Python tensor object identity.

## Restore

The accepted endpoint was relaunched as:

- tmux: `qwen36-tp4-gdn-reusequant-clone-envclean-32k`
- backend: `127.0.0.1:18080`
- health: OK
- active `_xpu_C` hash:
  `d2c6cc8d1cc92c3671a3a9357bed6c5783bdbcf505ee663d16f2e42f1e46ce8c`

## Next Steps

Do not pursue `view_as` as a safety barrier for GDN shared quant. If we return
to this area, test a different mechanism that can reduce clone overhead while
also separating storage or graph lifetimes, and keep the same rule: endpoint
speed gate first, then quality.
