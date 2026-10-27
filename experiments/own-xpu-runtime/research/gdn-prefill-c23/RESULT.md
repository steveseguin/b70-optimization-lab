# Multi-token GDN preparation (2026-10-27)

`OWNRT_GDN_PREP=1` now prepares every token's normalized Q/K and 48 gate values in one producer launch. The incumbent
6,144 recurrent-state subgroups per token consume those exact F32 values. Token order, state recurrence, arithmetic and
reduction trees are unchanged. Scratch scales as `tokens * 4192` floats; token-one behavior is unchanged.

## Card-23 rank-0 gate

- 192 CPU-device cases across 1/2/3/5 tokens, BF16/F32, packed/unpacked heads, aliases, gate boundaries and guards:
  1,242,767,616 bytes compared, zero mismatches.
- Three unprofiled interleaved 4096-token pairs, every pair exact across 1,029 target buffers and 71 draft allocations,
  with equal prefill/decode draft tokens. Zero GPU faults.
- Candidate binary: `ffd04f85103c85103dd1c1d0e27f3673093e361779d358c65e45f55e4f249c32`.

| Metric | B19 | Multi-token GDN_PREP | Change |
|---|---:|---:|---:|
| Rank-0 target prefill | 12.062 s | 10.485 s | **−1.577 s / −13.08%** |
| Whole prompt incl. draft replay | 17.177 s | 15.585 s | −1.592 s / −9.27% |

## Independent rank-1 reproduction

Canonical B24 binary `fffa34a38b87d34d0adc104831d4ec0b92d4bfebeab81c32b2c3725874c4ea49` matched B19 across all
1,079 target buffers and tokens on card 47. Prompt 17.301 → 17.154 s (−0.147 s / −0.86%). The smaller rank-1 gain does
not reduce the measured rank-0 result. Zero GPU faults.
## Service result

B24 passed both context oracles with zero differences, prefill 13/13, continuation and prior-build session
compatibility. Its 12-prompt suite matched B19 in every output and MTP statistic: 66.185 versus 66.205 tok/s (noise).
At 12.4K tokens the prompt fell from 52.45 to 47.58 seconds (−9.3%); the needle was found and continued equaled fresh.
Fresh decode measured 62.36 tok/s. B24 is the live engine.
