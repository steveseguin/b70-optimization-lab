# Qwen3.8 27B Q8 TP2 recurrent-quad SG24 workgroup

Date: 2026-08-17

Status: active; claimed on the reference ASRock host

Accepted SG16 (256 work items) improved two opposite-order endpoint pairs;
SG32 (512 work items) regressed `0.233%` in a fully complementary 16-process
screen. This midpoint trial packs 24 independent SG16 rows (384 work items)
per exact-shape recurrent GDN-quad workgroup.

The per-row Q8 DP4A walk, FP32 accumulation and subgroup reduction remain
unchanged. The experiment is target-only equal TP2 with F16 KV,
FlashAttention and `b1024/ub256`. It must announce SG24 on both devices and
end with `VERIFY_MISMATCH=0`. Screening will use complementary orders so SG16
and SG24 occupy the same process positions across the combined result. Any
quality mismatch or non-positive position-balanced result rejects the arm.

Other hosts should not duplicate this exact SG24 arm while the note is active.
