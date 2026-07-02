# Gemma 4 26B Q8: conditional-bonus verifier negative

Date: 2026-07-02

Status: closed negative. Do not promote, submit, or retest without a new
verifier design.

## Purpose

Test `LLAMA_SPEC_VERIFY_CONDITIONAL_BONUS_ARGMAX=1`, a default-off source path
that computes draft verifier rows in parallel and computes the bonus row only
after the draft rows match. The intent was to preserve the full-match bonus
pipeline while avoiding unnecessary bonus-row LM-head work.

This is still a Q8 target/verifier lane: target model remains
`gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`; the Q4_0 MTP draft is accepted only after
target verification.

## Artifacts

- Source snapshot:
  `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-conditional-bonus-source.patch`
- Smoke:
  `data/gemma4-q8-gpu0-condbonus-smoke2-20260702T001/summary.json`
- Four-lane A/B:
  - controls:
    `data/gemma4-q8-gpu0-control-condbonus-ab-20260702T0040Z/summary.json`,
    `data/gemma4-q8-gpu2-control-condbonus-ab-20260702T0040Z/summary.json`
  - candidates:
    `data/gemma4-q8-gpu1-condbonus-ab-20260702T0040Z/summary.json`,
    `data/gemma4-q8-gpu3-condbonus-ab-20260702T0040Z/summary.json`

The active source tree no longer contains `CONDITIONAL_BONUS` /
`conditional_bonus` symbols.

## Validity

All listed A/B lanes passed the fixed realistic cold gate:

- `cached_tokens=0` for every request;
- canary passed;
- `realistic_final_gate.passed=true`;
- target/verifier and quantization unchanged.

These are valid diagnostics but not LocalMaxxing candidates because they are
below the current `124.97714084813418 tok/s` record.

## Results

Primary metric: median generated-token throughput for tokens 1-100 after TTFT.

| lane | GPU | flag | median tok/s | p10 | mean |
|---|---:|---|---:|---:|---:|
| control | 0 | `0` | `115.634551` | `106.055722` | `115.647192` |
| candidate | 1 | `1` | `101.952750` | `92.791078` | `101.728023` |
| control | 2 | `0` | `112.705461` | `105.175846` | `114.151823` |
| candidate | 3 | `1` | `101.619378` | `97.334987` | `103.293294` |

The earlier smoke also passed but was slow:
`109.064762 tok/s` median tokens 1-100 after TTFT.

## Decision

Closed negative. Conditional bonus preserves correctness, but the extra
conditional path / bonus dependency costs more than the bonus-row work it can
avoid. This matches the broader verifier evidence: full-match-plus-bonus is
common enough that removing or delaying bonus work is not a record lever unless
it is part of a deeper row-adaptive verifier design that avoids real target
rows before LM-head work.

Future verifier work should not repeat conditional bonus, no-bonus, adaptive
bonus, late-head, prefix-tail, or post-hoc accept-prefix masking. The remaining
short-decode path is a real backend/graph redesign that preserves one target
decode boundary and computes only necessary rows without serial launches.
