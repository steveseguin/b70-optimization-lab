# Preregistration: A369-A373 - where the 33.7 ms two-row verify step goes on the exact-mode line

## Question

With the GDN verifier rows in the kernel extension's exact mode the two-row step is 33.7 ms
against 27.2 for one row (A340). On the old line the four zeroed blocks explained 29.5 of 42.7 ms
and the remainder doubled from 6.5 to 13.2 ms. Where is the 6.5 ms excess now, and what is the
largest per-row term left?

## Arms

MTP1 diag branch `f1d5cd88` (step timing + skip switches), stage v2, exact-mode exports, three
exact-2K rows each, ports 19982-19986: A369 control (no skip), A370 moe_gemm, A371 gdn_attn,
A372 qsa_attn, A373 hc_mix. Outputs change on skip arms (hashes differ from `afffd211…` by
construction; the control must hold it). Five-minute gaps between arms (host rule after the two
freezes).

## Predictions

Control 33.7 ms (A362/A363). MoE +2.6 ms per row as before (11.3 -> 13.9). GDN now near its
single-row 2.4 plus the exact-mode per-row work. QSA flat. HC near zero. Whatever remains in the
unattributed part is the next target; if MoE is the largest per-row term the lever is a
two-row-aware MoE dispatch, not attention.

## Stop rules

Control hash differs from `afffd211…`; server fails health. Skip arms are timing only.
