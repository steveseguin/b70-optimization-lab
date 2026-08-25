# Qwen3.6 Q4_K_M F16-KV TP1 MTP1 parent sentinel R2

Date: 2026-08-25. Status: **failed-do-not-expand on target parity**.

R2 fixed the R1 quality-client environment and reran both arms from fresh
create-only roots. Every terminal check except target-output parity passed.

| arm | 8K serving decode tok/s | output-token SHA-256 |
| --- | ---: | --- |
| MTP0 control | 22.467299998850997 | `8c686612...b124c` |
| MTP1 candidate | 30.06710373477709 | `b1cd1adc...1edc8` |

The candidate was `1.3382606604404959x` the control and its first exact request
accepted 59 of 67 generated draft tokens. Both exact-depth receipts passed,
but their deterministic 128-token outputs differed: the common prefix is 26
tokens, the first divergence is zero-based index 26 (the 27th token, control
`10551` versus candidate `96908`), and 102 of 128 aligned positions differ.
That repeats R1's parity failure with fresh receipts, so the apparent speedup
is not safe to expand or publish as a matrix speed.

The complete candidate quality battery did pass: all four exact canaries, both
repeat runs, the 8K needle, and cached-token-zero checks across all seven
requests. This is useful bounded quality evidence, but it cannot override the
pre-registered exact target-parity gate.

The terminal receipt is
`e66f2dee70ef017a46a25cb770c00b42d4409baca73c96cc752c612fef96fe8c`.
It says `failed-do-not-expand`; R2 fills zero site cells, authorizes no MTP1
curve, and changes no featured speed. That hash also matches
`validator.stdout.json`; it binds the terminal verdict, not the live overlay
manifest bytes. The validator checked known overlay invariants and references
but did not reject the additive unknown field described below.

One lifecycle blemish is disclosed rather than hidden. After the clean-tree
gate and temporary runner materialization, a collaborating agent added only an
explanatory capability-probe-environment field to the overlay manifest and
matching wrapper/note text. The temporary executable, model/runtime/client
identities, arms, requests, and scientific gates did not change. The terminal
validator read that additive field; the tracked files were restored
byte-identical to pushed main after completion. This means R2 was not a
pristine byte-exact preregistration execution. It cannot manufacture the
independently observed parity failure: the diagnostic observations remain
tied to the pinned temporary runner, but they grant no matrix, promotion, or
speed-claim authority.

The structured result is
[`../data/2026-08-25-qwen36-q4km-f16-tp1-mtp1-parent-sentinel-r2-result.json`](../data/2026-08-25-qwen36-q4km-f16-tp1-mtp1-parent-sentinel-r2-result.json).
