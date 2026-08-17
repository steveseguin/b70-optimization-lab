# Qwen3.8 27B Q8 TP2 recurrent-quad SG20/SG28 sweep

Date: 2026-08-17

Status: active; claimed on the reference ASRock host

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
non-positive balanced result closes that arm. Other hosts should not duplicate
this exact SG20/SG28 sweep while the note is active.
