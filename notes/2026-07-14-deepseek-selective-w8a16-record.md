# DeepSeek V4 selective W8A16 record

Global small-M W8A16 was fast but failed the frozen long-math invariant. The
failure was not a remaining weight-scale transpose bug: all five real dense
projection shapes passed direct dequantized-reference tests, and each shape
also solved the invariant when enabled alone. The failure was an accumulated
arithmetic-drift threshold across 215 changed projections per decode token.

An exact `N x K` environment allowlist isolated the five module families. On
the same current graph/MHC stack, W8A8 screened at `29.8992 tok/s`. Individual
W8A16 screens reached `30.6770` for fused WQA/WKV, `30.1165` for Q-B,
`30.4181` for O-B, `30.7761` for shared gate/up, and `30.0792` for shared
down. Every individual lane returned `101! - 1` on the frozen 768-token test.

The promoted lane enables W8A16 for the first four shapes and keeps shared-down
on canonical W8A8. Shared-down was the smallest speed contributor and the most
logit-disruptive individual lane. This selective boundary reached strict cold
medians of **`33.433875`** and **`33.363231 tok/s`**, versus the prior valid
`30.340369` record. The first run's p10 was `32.861961`; every row was a unique
cold prompt with `cached_tokens=0` and valid streamed-token timing.

Sequential graph replay returned `1073 -> 437 -> 1073`; exact-copy, Paris,
strict-JSON, the long invariant, and all executable quality gates passed. The
first 80 greedy positions matched same-stack W8A8 at 83.75%, with 80.81% mean
top-20 overlap. K160 still has an intermittent CJK-corruption floor in both
W8A8 and W8A16 quality captures; two high4 captures flagged three prompts and
then one, so this remains an explicit model/runtime caveat rather than being
silently treated as solved.

LocalMaxxing approved the new single-session TP4 record as
`cmrlb675r0705mj01k9psoub0`. The important lesson is that a globally faster
numeric path can be recovered safely by selecting projection families according
to measured end-to-end value and recurrent sensitivity, not by assuming that
one arithmetic mode must cover every dense layer.

Structured evidence is in
`experiments/deepseek-v4-flash-reap-xpu-b70/data/w8a16-shape-isolation-20260714.json`.
