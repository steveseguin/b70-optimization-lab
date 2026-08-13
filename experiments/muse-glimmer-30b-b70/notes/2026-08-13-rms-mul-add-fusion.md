# SYCL RMSNorm + scale + residual fusion

Date: 2026-08-13

## Result

Source commit `5f71bed9b` adds a default-off
`GGML_SYCL_RMS_NORM_MUL_ADD_FUSION=1` path. It extends the existing exact
RMSNorm-plus-scale kernel through the adjacent residual ADD, eliminating one
launch at 103 direct post-allreduce layer boundaries per target pass. The
recursive-doubling F32 allreduce is unchanged. A stored F32 intermediate is
reloaded through a volatile pointer before the residual add to preserve the
old kernel boundary's rounding and operand order.

The short hit proof emitted:

```text
SYCL RMSNorm+MUL+ADD fusion active: tensor=ffn_inp-0 rows=2 cols=6656
```

It retained the same three 64-token hashes as the prior committed-prefix
smoke. The full 256-token C/A/C produced canonical hashes in every arm.

| Arm | Prose | Code | JSON | Mean tok/s |
| --- | ---: | ---: | ---: | ---: |
| control before | 56.144 | 84.075 | 98.792 | 79.6703 |
| fusion candidate | 56.273 | 81.433 | 99.151 | **78.9523** |
| control after | 55.989 | 81.081 | 98.908 | 78.6593 |

The first control had a different proposal history (`781/199` on code versus
the candidate/control-after `811/197`) and is not a clean timing comparator.
Candidate and control-after drafted/accepted counts match exactly in all
classes. Against that matched control the gain is `+0.3725%`, with per-round
savings of `0.275 / 0.231 / 0.129 ms` for prose/code/JSON. Retain this as an
exact micro-win, not as the missing multi-millisecond century lever.

The raw candidate itself is the new exact campaign high-water mark at
`78.952 tok/s`, narrowly above the committed-prefix result. The honest
`>100 tok/s` objective remains unmet.

## Evidence

- smoke config: `sweeps/20260813-rms-mul-add-fusion-smoke.json`;
- full C/A/C config: `sweeps/20260813-rms-mul-add-fusion-final-cac.json`;
- smoke JSONL SHA256:
  `12d4082c642d8e60d7b1d96eca48c08ebed996f3a47d313fd65ccdba9a34aa17`;
- full C/A/C JSONL SHA256:
  `de4e8256358c72e6f99c2d8979102c224b268394ad966395c1268064cb4cbc16`;
- smoke log SHA256:
  `c9f4383a210a1809677da88171f44e2c1f295a8bd71f781e44accd7a36f05675`;
- control-before/candidate/control-after log SHA256:
  `32be05b770269b1b887c9fe0ad8cba5eb79517df1b4f859cab72783acf027081`,
  `bf506c55494c0778cde7933b781993454cd5860c14e38e4100cc7b3169a57c5e`,
  and `94041e7e877d1c8c4d64a9c7b926b025bcc8aa84e5e42c3125b36be3268d778e`.

Production was restored without reboot and passed the full model,
cache-zero code, and vision gate in
`data/muse-health-20260813-rms-mul-add-fusion-restore.json`.

## Decision

Retain the source commit and flag. It is exact and positive on the matched
comparison, but too small to enable in production or to justify a claim that
kernel fusion alone reaches 100. Continue the same-width budget-15 DDTree plus
kernel campaign; on the current round times the optimistic DDTree ceiling is
about `95.8 tok/s`, still requiring roughly `2.2 ms/round` more exact savings.
