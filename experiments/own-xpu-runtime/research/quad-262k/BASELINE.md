# Quad native 262K baseline (2026-10-27)

Four-stage `[0,12,24,36,48]` on PCI `23/27/43/47`, using B24 arithmetic and a checked 262,144-position RoPE table.

## Foundation

- 4K four-stage and matched two-stage target-only runs: identical 32 output tokens and complete committed target state.
- 64K runs: same result. Device totals: 13.73, 14.13, 15.09 and 15.91 GB.
- Native 262K run: all four stages completed, identical output tokens, no faults and return code 0. Wall time 343.05 s.
- 262K device totals: 16.60, 17.00, 17.96 and 18.78 GB, all below the 30 GiB per-card cap.
- `rope-262144.bf16`: 33,554,432 bytes, SHA256 `e53a22a0792ef60aa6c5ebb7db7f30749b577f6cc355b661dd4ea31da5ee63bc`;
  its first 8,388,608 bytes equal the 64K table exactly.
- Canonical binary: `a33579eccb92822d1d905c9ad2c0ebfdb5937499fd16b0309e62d04bbce67ba8`.

No quad speed claim or independent 262K oracle comparison is made. Two-stage 262K placement does not fit the current
per-card cap. Further validation must cover long-prompt state, continuation, sessions and performance.
