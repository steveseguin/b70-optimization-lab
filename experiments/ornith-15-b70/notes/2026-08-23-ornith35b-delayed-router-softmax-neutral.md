# Ornith 1.5 35B-A3B: delayed router softmax is engine-neutral

Date: 2026-08-23 EDT

Status: **CLOSED ENGINE-NEUTRAL — do not ship**

Ornith's Qwen-derived MoE router computes a 256-element softmax, selects the
top eight experts, and normalizes the selected weights again. Mathematically,
the first full softmax is redundant: raw logits have the same ordering and a
softmax over only the selected eight produces the same normalized expression.

A strict default-off candidate reused the existing delayed-softmax top-k mode
only for the exact one-token Ornith shape: softmax routing, normalization,
256 experts, and top-8. It selected from raw logits and evaluated softmax only
over the selected values instead of all 256.

## Correctness

The same frozen binary produced byte-identical forced 128-token continuations
with the flag off and on. Both extracted transcripts had SHA-256
`6b548046111bb3da022d917ee3b3285a60b14299e2b67a6e02da0ddc864809f9`.
The candidate recorded 5,080 intended router hits. This is a same-command
control hash; it differs from an older package hash because this invocation
retained the model's reasoning preamble.

## Mirrored engine result

Depth-zero `tg128`, seven repetitions, same binary, A/B/B/A:

| arm | decode tok/s | within-run standard deviation |
| --- | ---: | ---: |
| control A | 134.717980 | 1.774457 |
| candidate A | 134.454561 | 1.845043 |
| candidate B | 134.303263 | 1.684891 |
| control B | 134.194221 | 2.443906 |

Control mean was 134.456101 tok/s and candidate mean was 134.378912 tok/s,
or **-0.0574%**. The change is neutral within noise and fails the rule that
both candidates must exceed both bracket controls. It did not earn a server
screen. No value is extrapolated.

The exact but neutral candidate is retained at
`../patches/llamacpp-ornith15-delayed-router-softmax-neutral-20260823.patch`.
The accepted source and published executable hashes were restored after the
screen. Structured and raw evidence share the
`2026-08-23-ornith35b-delayed-router-softmax-` prefix in `../data/`.
