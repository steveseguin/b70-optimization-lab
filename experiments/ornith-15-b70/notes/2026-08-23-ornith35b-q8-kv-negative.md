# Ornith 1.5 35B-A3B: Q8_0 KV cache is much slower on B70

Date: 2026-08-23 EDT

Status: **CLOSED QUALITY/PERFORMANCE NEGATIVE — keep F16 KV**

Q8_0 K/V was screened as a possible lower-memory packet variant. It is not an
exact substitute: the fixed-seed 128-token transcript changed from canonical
`2e7965fcdc273f0433df359cff5188ae3585426fd32f28536121d1b5e35dad18`
to
`7a8f2fb116ea7ecbde336462865c4ac0d15a8fcbd8efee33ba2536456393e012`.

The standard no-extrapolation depth harness then measured Q8_0 explicitly at
8K and 32K existing context. The comparison below uses the previously
published same-model, same-binary, same accepted-stack F16 sweep; because the
arms were not interleaved in one session, it is a decisive branch screen, not
a fine-grained matched A/B claim.

| Existing context | F16 KV tg128 (tok/s) | Q8_0 KV tg128 (tok/s) | Q8_0 delta |
| ---: | ---: | ---: | ---: |
| 8,192 | 124.209778 | 82.198718 | **-33.82%** |
| 32,768 | 96.995532 | 39.868771 | **-58.90%** |

Q8_0 also measured pp2048 at 1,347.12 tok/s (8K depth) and 1,133.65 tok/s
(32K depth), but decode is the decision metric for this branch. Its large,
increasing decode regression does not justify a quality-validation campaign or
a user-facing Ornith packet on this hardware. Keep `--cache-type-k f16` and
`--cache-type-v f16`.

Raw CLI and sweep records are under `../data/ornith-kv-q8*`; the structured
decision is `../data/2026-08-23-ornith35b-q8-kv-summary.json`.
