# Packet 26 W2 control, cards 2+3 (2026-10-11 22:03 UTC): 12.08 tok/s, exact, and the cards are the limit

Packet 18's specialised kernels with packet 26's host path (ordered lookup, plan-time
binding resolution), R5 GEMV dispatch, wall-clock timing only. 64/64 tokens and 384/384
layer fixtures equal to the v2 oracle; clean kernel log.

Per generated token (median of tokens 10–64): 81.6 ms wall; the host needs **10.4 ms**
to issue the 2,181 launches (41 ms before the host-path work) and then waits
**70.6 ms** for the cards. Decode speed is therefore unchanged at 12.08 tok/s: the token
is GPU-bound, and only faster kernels move it now.
