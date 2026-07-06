# Qwen27 Draft-INT4 Deeper MTP / ReplaySSM Cache-Length Screen: No Win

Date: 2026-07-06

Classification: strict fresh diagnostic screen, quality disabled, no promote,
no LocalMaxxing.

## Purpose

The current valid Qwen27 record uses ReplaySSM exact GDN state handling,
runtime INT8 target LM-head BF16 scales, runtime INT4 draft LM-head BF16
scales, ordinary MTP3, `max_cudagraph_capture_size=8`, and
`VLLM_XPU_GDN_REPLAYSSM_SPEC_CACHE_LEN=8`.

MTP3 branch/regenerate cost modeling showed a hard no-extra-cost ceiling near
`102 tok/s` at the current verifier-step cost. To get a real path toward
`125+`, we need either lower step cost or more verified tokens per step. This
screen retested deeper ordinary MTP on the current record family and isolated a
ReplaySSM ring-cache blocker.

Every completed endpoint row used the fixed realistic Qwen suite, one cold
response per prompt, `cached_tokens=0`, token-id timing, and no
prompt/KV/history reuse. `RUN_QUALITY=0` because no candidate beat the current
record or created a promotable row.

## Common Runtime

- model: `webhie/Qwen3.6-27B-int4-AutoRound`
- TP1, one B70 per candidate, four candidates in parallel
- XPU graph on
- ReplaySSM exact GDN path:
  `VLLM_XPU_GDN_REPLAYSSM_SPEC=1`,
  `VLLM_XPU_GDN_REPLAYSSM_COMMIT_IN_FORWARD=1`,
  `VLLM_XPU_GDN_REPLAYSSM_SLOT_MGMT_TORCH_FALLBACK=1`
- target LM-head: runtime INT8 with BF16 scales
- draft LM-head: runtime INT4, group size 128, BF16 scales
- suite: `repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json`

## Failed First Retest

The `depthcur2` retest initially kept
`VLLM_XPU_GDN_REPLAYSSM_SPEC_CACHE_LEN=8` while asking for deeper speculation.
MTP4 and MTP5 failed before readiness:

- MTP4: `got 8 < 10`
- MTP5: `got 8 < 12`

This is expected from the source contract in
`/home/steve/src/vllm/vllm/model_executor/layers/mamba/gdn_linear_attn.py`:

- `_xpu_gdn_replayssm_cache_len()` requires
  `ring_len >= 2 * max_spec_len` (lines 128-146 at test time);
- `max_spec_len` is effectively `num_speculative_tokens + 1`, so MTP4 needs a
  ring of at least `10`, rounded to power-of-two `16`; MTP5 needs at least
  `12`, also rounded to `16`.

The MTP3/cache8 control from the same retest remained healthy:

| Label | Median tok/s | p10 | Mean | Gate |
| --- | ---: | ---: | ---: | --- |
| `qwen27-draftint4-depthcur2-mtp3-cg8` | `68.06979577361167` | `62.30723628237865` | `68.03519580632152` | pass |

## Corrected Cache-Length Retest

The corrected `depthcur3` retest explicitly set cache length by candidate:

| Label | MTP / graph / ReplaySSM cache | Median tok/s | p10 | Mean | TTFT median ms | Gate |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `qwen27-draftint4-depthcur3-mtp3-cg8-cache8` | MTP3 / cg8 / cache8 | `66.76968913048438` | `61.99557818904642` | `67.04647998313693` | `487.5629140296951` | pass |
| `qwen27-draftint4-depthcur3-mtp3-cg8-cache16` | MTP3 / cg8 / cache16 | `12.519339831407972` | `11.420150942577374` | `12.471794121879464` | `660.0791530217975` | pass |
| `qwen27-draftint4-depthcur3-mtp4-cg8-cache16` | MTP4 / cg8 / cache16 | `12.751685172119899` | `11.459149129191992` | `12.815401419397922` | `752.4342375108972` | pass |
| `qwen27-draftint4-depthcur3-mtp5-cg16-cache16` | MTP5 / cg16 / cache16 | `12.262814451537484` | `11.822558977012346` | `12.960018394310202` | `848.1418300652876` | pass |

Tracked compact summaries:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-draftint4-depthcur2-mtp3-cg8-candidate-summary-20260706T071509Z-depthcur2.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-draftint4-depthcur2-mtp4-cg8-candidate-summary-20260706T071509Z-depthcur2.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-draftint4-depthcur2-mtp5-cg8-candidate-summary-20260706T071509Z-depthcur2.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-draftint4-depthcur2-mtp5-cg16-candidate-summary-20260706T071509Z-depthcur2.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-draftint4-depthcur3-mtp3-cg8-cache8-candidate-summary-20260706T071851Z-depthcur3.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-draftint4-depthcur3-mtp3-cg8-cache16-candidate-summary-20260706T071851Z-depthcur3.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-draftint4-depthcur3-mtp4-cg8-cache16-candidate-summary-20260706T071851Z-depthcur3.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-draftint4-depthcur3-mtp5-cg16-cache16-candidate-summary-20260706T071851Z-depthcur3.json
```

Raw full bench payloads were left ignored because the compact summaries and
raw server/log paths above are enough to preserve the result.

## Interpretation

The important result is not that MTP4/MTP5 lost; it is that **cache16 alone**
collapses the current ReplaySSM path. MTP3/cache8 stayed in the normal
`66-68 tok/s` band. MTP3/cache16, with the same speculative depth, fell to
`12.5 tok/s`. MTP4/cache16 and MTP5/cache16 stayed in the same collapsed
`12-13 tok/s` band.

The likely source explanation is the native ReplaySSM fast path in
`gdn_linear_attn.py`: at test time it only entered
`torch.ops._xpu_C.gdn_replayssm_spec_decode` when `max_spec_len <= 4` and
`max_cache_len in (2, 4, 8)` (lines 995-1001). Cache length `16` therefore
falls out of the fast path and pays the slow generic path even for ordinary
MTP3.

## Decision

No endpoint candidate.

Do not repeat config-only MTP4/MTP5/deeper-MTP sweeps on the current
ReplaySSM/draft-INT4 recipe while cache16 is outside the optimized native path.
Future deeper-spec work first needs a source/kernel change that keeps
ReplaySSM cache length `16` on a fast exact path, then a same-window retest:

1. MTP3/cg8/cache8 control;
2. MTP3/cg8/cache16 isolation;
3. MTP4/cg8/cache16;
4. MTP5/cg16/cache16.

Only after cache16 no longer collapses should deeper MTP acceptance and quality
be re-evaluated.
