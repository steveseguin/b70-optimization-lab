# Qwen3.8 UD-Q4_K_XL TP1 q8_0 KV estimate v1

## Classification and scope

This is a frozen **grade-D estimate**, not a measurement. It fills only the
Qwen3.8 UD-Q4_K_XL TP1, MTP0, graph-off, q8_0-KV decode curve at exact active
context depths `0/2048/4096/8192/16384/24576/32768`. It does not estimate
quality, TTFT, VRAM, serving throughput, or record eligibility, and it must not
be transferred to another revision, artifact, TP, MTP depth, graph mode, KV
type, runtime, workload, or hardware.

The structured snapshot is
`data/qwen38-q4kxl-q8-tp1-context-estimate-v1.json`. Rebuild it with:

```bash
python3 -B tools/qwen38_q4kxl_q8_estimator_v1.py --check
python3 -B tools/test_qwen38_q4kxl_q8_estimator_v1.py
```

## Frozen method

At each exact context depth, the estimator computes the observed q8_0/f16
decode ratio for two within-Qwen3.8 donors:

- Q4_K_M, with matched f16 and q8_0 depth sweeps;
- UD-Q5_K_S, with the retained f16 depth sweep and q8_0 flagship raw sweep.

It applies the geometric mean of those ratios to the measured UD-Q4_K_XL f16
anchor:

```text
central = Q4XL_f16 * sqrt(
    (Q4KM_q8 / Q4KM_f16) *
    (Q5KS_q8 / Q5KS_f16)
)
```

The uncertainty band is the two donor predictions:

```text
lower = Q4XL_f16 * min(Q4KM_ratio, Q5KS_ratio)
upper = Q4XL_f16 * max(Q4KM_ratio, Q5KS_ratio)
```

This envelope is not a statistical confidence interval. It captures donor
disagreement only; true model-form error can be larger. The formula is bounded
to exact shared depths and performs no interpolation or extrapolation.

## Estimated decode curve

| active context | f16 anchor | q8_0 estimate | donor envelope |
|---:|---:|---:|---:|
| 0 | 21.810 | 21.534 | 21.335–21.735 |
| 2K | 21.530 | 19.991 | 19.761–20.225 |
| 4K | 21.370 | 18.815 | 18.550–19.085 |
| 8K | 21.060 | 16.771 | 16.509–17.037 |
| 16K | 20.490 | 13.424 | 13.181–13.672 |
| 24K | 19.950 | 11.276 | 11.034–11.523 |
| 32K | 19.450 | 9.756 | 9.524–9.994 |

All rates are raw-engine decode tok/s for the retained `llama-bench tg128`
shape. These values must display as estimated and grade D wherever consumed.

## Fail-closed prefill decision

Prefill is deliberately not estimated. The Q4_K_M q8/f16 prefill ratios stay
near `0.99`, while the UD-Q5_K_S ratios range from about `1.07` to `1.20` and
come from a separately identified build. That disagreement is too confounded
to support a defensible central estimate. The JSON retains both donor ratios
but marks every prefill point `missing`.

## Frozen identities

- estimator: `qwen38-q4kxl-q8-context-estimator` version `1.0.0`;
- estimator SHA-256:
  `1b12ff6b5b878cf8d0f3f276ce86b6eb91c4d2819b5cd9672a550118d3e3cc8d`;
- target artifact:
  `unsloth/Qwen3.8-27B-GGUF@4ca720788d1e01f1bff70c033e0d0028fd02e502`,
  `Qwen3.8-27B-UD-Q4_K_XL.gguf`, SHA-256
  `3f227079003add2511437e5b1e94812e363385225bf6a9b47b0054a72bc8b01e`;
- Q4_K_M matched-KV source SHA-256:
  `1c439bc6e46dc29ba37ed234ceb5a52758a68a10f570dc4d3efa0a03d33aa6ca`;
- f16 weight-ladder source SHA-256:
  `219331863fd0dee7f14f705890f373c1208b9a45d8f6d54e5e6ae2fde0ee4c26`;
- UD-Q5_K_S q8_0 source SHA-256:
  `8f05570d712f6687bf359cfbda59d2cfb1bf31b3f573fc544f7b79f600accc09`;
- model-manifest source SHA-256:
  `7e7beaa9264400082c8ac50b6db9a50bc36ca44319d0bb6c921d923c38e285ee`.

The script rejects any source hash or model-identity mismatch before producing
values. The snapshot has no wall-clock generation field, so regeneration is
byte-for-byte deterministic.
