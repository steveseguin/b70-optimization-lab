# Packet 38 on cards 2+3 (2026-10-12 20:28 – 21:12 UTC): independent repeat, median 38.11 tok/s, every request exact

The same sealed binaries on the other pair of cards, a fresh chain (suffix `d`/`e`: K0,
K1a, K1b, K2, W0p, KD), then the development prompt and the twelve-prompt suite, two
repeats. Clean kernel log. The host was running three CPU model jobs at the time (load
average 8–11); the decode windows were pinned to the reserved cores.

| | Cards 0+1 (16:04–16:41 UTC) | Cards 2+3 (this run) |
| --- | ---: | ---: |
| Development prompt, draft head, native controller | 39.05 tok/s | **38.81 tok/s** ([receipt](W2m-native-d/receipt.json)) |
| Twelve prompts x two repeats: requests exact | 24 of 24 | **24 of 24** ([summary](WS-d/summary.json)) |
| Suite median | 38.25 tok/s | **38.11 tok/s** |
| Suite range | 35.05–41.43 | 34.77–41.19 |

Request by request the second pair is 0.65% slower in the median (−1.6% to +0.4%). The
kernel selection measured on card 2 equals the one measured on card 0 except for one
small class (HC inject: `p33.dense.segment` here, `p28.dense.wg32` there).

Time to first token over the suite (prompt reading plus the first generated token,
after the unmeasured warm-up request): median 1.42 s, 1.25–1.88 s.

The wrapper used here is the amended one that can also take the 128-token manifest; the
native binaries are unchanged and still refuse more than 64 generated tokens, so the
128-token suite is not run with this packet.

One stop on the way: the first K2 of this chain measured correctly and then failed its
compression step against the packet-local storage cap again (the build tree had grown
to 5.4 GB with retained compressed outputs of earlier windows); superseded raw outputs
were removed ([list](../../DISK-CLEANUP-20261012.txt)) and K2 rerun as `K2e`.
