# Ornith 1.5 35B-A3B: the 9B Q8 model is too slow to serve as its draft

Date: 2026-08-23 EDT

Status: **CLOSED BEFORE FULL LOAD — analytical suitability rejection, not a throughput result**

The common Ornith/Qwen lineage and vocabulary make Ornith 1.5 9B a natural
compatibility candidate for assisted decoding of Ornith 1.5 35B-A3B. Its
measured speed makes the pairing structurally unsuitable on one B70, however.
The existing one-card 9B Q8 target-only diagnostic is `50.109 tok/s`, or about
`19.96 ms/token`; the accepted 35B stack's fresh-server mean is `115.680
tok/s`, or about `8.64 ms/token`.

Even an impossible best case cannot win. With four draft tokens per cycle,
perfect acceptance, a free target verifier, and one extra target token emitted,
the upper bound is only `5 / (4 × 19.96 ms) = 62.64 tok/s`. Real verification,
synchronization, and sampling only reduce that figure.

A bounded combined-load probe was started with the accepted 35B runtime, a 2K
context, both models assigned to one B70, and a 15 GiB host-memory cap. The 35B
target reached 20,370.9 MiB resident VRAM without a GPU fault. The NFS-backed
9B load was then stopped intentionally once the speed bound was established;
no combined model execution or performance result is claimed.

Do not retry this exact pairing as a performance lane. Assisted Ornith work
needs a substantially smaller, faster, vocabulary-compatible draft. Keep any
future target-only and assisted figures in separate rows.
