# 2026-06-29 FA-on 32K/VMM Depth/P-Min Screen

Status: **closed negative**. Do not full512-confirm or submit.

Purpose: after the accepted `121.41411987308553 tok/s` FA-on 32K/VMM baseline
record, check whether the current record identity changed the old conclusion
that deeper MTP (`n_max=4`) and nearby `p_min` tweaks lose on the fixed
realistic suite.

All lanes used:

- llama.cpp `c926ad098` dirty Gemma record stack;
- `UD-Q8_K_XL` target/verifier with Q4_0 MTP draft;
- one B70 replica, `CTX_SIZE=32768`, `FLASH_ATTN=on`,
  `GGML_SYCL_ENABLE_VMM=1`;
- VDR2 selected-down fused weighted-sum, F16 p021 small-ncols, bulk sampled-ID
  verifier host read;
- fixed realistic prompt suite, each prompt once, `cached_tokens=0`;
- no prompt/KV/context/response reuse, n-gram/history acceleration, or warmed
  repeated prompt averaging;
- `MAX_TOKENS=128` strict screen only.

## Results

| GPU | Variant | Summary | Gate | Canary | Median 1-100 | p10 | Mean | Full128 | Wall128 | TTFT |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | control: `n_max=3`, `n_min=2`, `p_min=0.0475` | `data/gemma4-q8-gpu0-faon-vmm-depthscreen-control-strict128-20260629TnextA/summary.json` | pass | pass | 119.79709987498046 | 105.30127989000863 | 118.4090374578642 | 112.9163744914563 | 96.68289780009532 | 178.64990246016532 |
| 1 | `n_max=4`, `n_min=2`, `p_min=0.0475` | `data/gemma4-q8-gpu1-faon-vmm-depthscreen-n4-p00475-strict128-20260629TnextA/summary.json` | pass | pass | 109.04088486396341 | 93.59618475637703 | 107.69901722144817 | 110.35451325563503 | 93.71948896763 | 179.60925353690982 |
| 2 | control repeat: `n_max=3`, `n_min=2`, `p_min=0.0475` | `data/gemma4-q8-gpu2-faon-vmm-depthscreen-control2-strict128-20260629TnextA/summary.json` | pass | pass | 119.51944277144372 | 104.53231137262748 | 116.99729571552666 | 118.46564893106533 | 98.56883701583968 | 180.50502793630585 |
| 3 | `n_max=3`, `n_min=2`, `p_min=0.0500` | `data/gemma4-q8-gpu3-faon-vmm-depthscreen-n3-p0050-strict128-20260629TnextA/summary.json` | pass | pass | 115.0386426314836 | 107.40502665251725 | 115.99804034019776 | 113.79073112264032 | 97.90709029624153 | 179.18110394384712 |

## Decision

Both candidates lost to same-window controls:

- `n_max=4` is still a broad regression under the current FA-on 32K/VMM record
  identity, despite preserving validity.
- `p_min=0.0500` improved p10 versus one control but lost the primary median
  metric and does not justify full512 promotion.

This reinforces the current record shape: `n_max=3`, `n_min=2`,
`p_min=0.0475`, `UBATCH_SIZE=1024`. Future work should return to source-level
verifier cost reduction rather than MTP-depth or threshold tuning.

Follow-up: `20260630-faon-vmm-pmin-gap-screen-negative.md` closed the remaining
small p_min gaps (`0.04625`, `0.04725`, `0.047625`, `0.04875`) under the same
FA-on 32K/VMM selected-down VDR2 identity. Best lane was `0.047625` at
`118.41776692242152 tok/s` strict128, still below the `0.0475` controls above.
Do not reopen isolated p_min screens without a new source mechanism.
