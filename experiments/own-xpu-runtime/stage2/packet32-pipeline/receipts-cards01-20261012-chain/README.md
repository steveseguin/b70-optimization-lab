# Packet 32 on cards 0+1 (2026-10-12 01:32 – 02:19 UTC): both cards working at once, exact

Two rank processes, one card each, connected only by a small shared file. K0, K1a, K1b,
K2, the new concurrency canary W0p and two full-model runs passed through the packet's
own wrapper; clean kernel log (no `xe` line) throughout.

| Window | What it shows | Result |
| --- | --- | --- |
| [W0p](w0p-r32/receipt.json) | both processes alive and issuing at once: 1,000 hand-overs, 1,000 chained kernels per rank | passed; 995 of 1,000 host work intervals overlapped; 0.14 ms per hand-over |
| [W2s](w2s-r32/receipt.json) | sequential generation in the new process model (prompt overlapped) | **64/64 tokens, 384/384 layers; 19.47 tok/s** (51.4 ms per token; median interval 48.4) |
| [W2d](w2d-r32/receipt.json) | **diagnostic only**: guesses fed from the oracle's tokens, so every guess is right: the pipeline's ceiling | **64/64 tokens, 384/384 layers**; 63 of 63 guesses kept; 26.2 ms per token mean, 24.1 median (38.1 / 41.5 tok/s as an interval rate, not a speed result) |

What this establishes:

1. **Two cards can run at the same time under our runtime.** With a right guess the
   first card works on position p+1 while the second finishes p; a token then costs one
   half (22.8 and 23.1 ms of host-observed work per rank) plus about 1.5–3 ms of
   coordination, instead of both halves in sequence.
2. **Output is unchanged.** Tokens and all retained layer bytes equal the v2 oracle in
   both modes; the rollback path (37 alternate buffers, no bulk copies) is exercised by
   the CPU gates with forced misses.
3. **The host-memory shadow of the two-card process is gone.** After loading, the
   kernel's GPUActive counter is 17 MB and MemAvailable is unchanged at 116 GB; the
   one-process runtime held 55.3 GB there and pushed MemAvailable down to 63 GB
   ([packet 29](../../packet29-merged/receipts-cards01-20261012-chain/README.md)).
4. **What the sequential mode costs here:** 51.4 ms per token against 44.3 in the
   one-process runtime with the same kernels: the two halves take 23.8 + 23.4 ms and the
   Python controller adds about 4 ms per token (0.4–0.7 ms per command). The controller
   should move into the native processes.
5. **First position:** each rank compiles its kernels on first use, about 17 s per
   rank, so the 87-token prompt took 36–41 s of which 34 s is that one-time cost.

Timing model with these numbers: a right guess costs about 24–27 ms plus the time to
compute the guess, a wrong one about 47 ms. With a guesser that is right 70% of the time
and costs 3 ms that is about 34 ms per token (about 30 tok/s) before any further kernel
or host-path gain; the reference is 28.49 tok/s. The real guesser (the model's official
draft head, [packet 36](../../packet36-draft/README.md)) is being built;
[packet 31](../../packet31-mtp-acceptance/README.md) measures its agreement on CPU.
