# Qwen3.8 27B Q8 TP2 recurrent-quad SG20/SG28 sweep

Date: 2026-08-17

Status: closed; SG20/SG28 rejected, retain SG24

Accepted SG24 packs 24 independent SG16 output rows (384 work items) in the
exact recurrent GDN-quad workgroup and beat accepted SG16 in two opposite-order
endpoint pairs. SG32 regressed in the fully position-balanced direct screen.
This follow-up brackets the observed optimum with SG20 (320 work items) and
SG28 (448 work items).

The model, Q8 layout, DP4A row body, FP32 accumulation/reduction order, equal
TP2 split, F16 KV, FlashAttention, and `b1024/ub256` remain unchanged. Only the
number of independent SG16 rows sharing the exact local
`K5120/N5120+3072+24+24` workgroup changes. Both candidate doors must announce
on both devices and finish with `VERIFY_MISMATCH=0`.

The first gate is a same-binary complementary-position `p64/n256/r3` screen
against promoted SG24. A candidate must beat SG24 after pooling opposite arm
positions before receiving an endpoint suite. Any quality mismatch or
non-positive balanced result closes that arm.

## Result

Both smokes announced the intended branch on both B70s and ended at
`VERIFY_MISMATCH=0`. The 12-process three-arm Latin screen placed every arm in
two odd and two even positions across the run:

| Arm | Four-process mean | Median | Delta vs SG24 |
| --- | ---: | ---: | ---: |
| SG20 | `37.101743` | `37.060270` | `-0.070%` |
| SG24 control | `37.127787` | `37.038971` | control |
| SG28 | `37.247675` | `37.339831` | `+0.323%` |

SG28 beat SG24 in both two-sample halves of that screen and therefore advanced
to the predeclared 16-process complementary head-to-head. It did not confirm:

- first eight-run position block: SG28 `37.153688` versus SG24 `37.386397`
  tok/s (`-0.622%`);
- exact complementary block: SG28 `37.418311` versus SG24 `37.388489` tok/s
  (`+0.080%`);
- combined unbiased 16-run mean: SG28 `37.286000` versus SG24 `37.387443`
  tok/s (`-0.271%`).

All 28 screening/confirmation processes ended with `VERIFY_MISMATCH=0`; both
GPUs remained normal and no Xe fault/reset/hang appeared. The performance gate
failed, so no endpoint or semantic suite was warranted. Retain promoted SG24
and do not repeat SG20 or SG28 unchanged.

Artifacts:

- structured result:
  [`../data/2026-08-17-q8-recurrent-quad-sg20-sg28-negative.json`](../data/2026-08-17-q8-recurrent-quad-sg20-sg28-negative.json)
- focused increment after accepted SG24:
  [`../patches/q8-recurrent-quad-sg20-sg28-negative-20260817.diff`](../patches/q8-recurrent-quad-sg20-sg28-negative-20260817.diff)
