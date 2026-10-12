# Packet 36 on cards 0+1 (2026-10-12 05:24 – 05:56 UTC): the official draft head on the card; 30.37 and 31.02 tok/s, exact

The two-process pipeline of packet 32 with the model's official one-token draft head as
the guess provider on the second card's process (label: official draft head, draft-only
8-bit requantisation of its experts, output identical to sequential decode). K0, K1a,
K1b, K2, W0p, KD and two W2m runs passed through the packet's wrapper under the suffix
`r36e`; clean kernel log (no `xe` line).

| Window | Result |
| --- | --- |
| [KD](kd-r36e/window.json): draft head on the second card against the host implementation, two fresh owners | 460 of 460 files byte-equal in each owner (per-position draft state, logits, final cache) |
| [W2m](w2m-r36e/receipt.json): full two-card decode, `--draft mtp` | **64/64 tokens, 384/384 layers equal to the v2 oracle; 30.37 tok/s** (63 tokens in 2,074.7 ms) |
| [W2m, second fresh pair of processes](w2m2-r36e/receipt.json) | **64/64, 384/384; 31.02 tok/s** |

Details of the first run (the second is the same within 2%):

- **53 of 63 guesses right (84%)** on this prompt, the same 53 in both runs (the draft is
  deterministic). CPU measurement over four prompts: 77.7%.
- A right guess costs **28.7 ms** on average (median token interval 27.8 ms): 4.2 ms for
  the draft (1.9 ms for its layer, 2.3 ms for the full output head) before the second
  card starts its half, then one half (22.8 / 23.1 ms). A wrong guess costs **55.3 ms**
  on average: the redo of the first half plus the second half, and in some cases the
  remainder of the wrong half, which is not cancelled yet.
- Mean 32.9 ms per token against 51.4 ms for the same runtime without guesses
  (packet 32, 19.47 tok/s) and 44.3 ms for the one-process runtime (packet 29).
- Draft allocations on the second card: 3.35 GB (output head shared with the target);
  27.3 GB of card memory resident after loading on that card. Host memory: no shadow
  (GPUActive 17 MB, MemAvailable 114 GB).

**What this is and is not.** It is the first bit-exact run of our runtime above the
28.49 tok/s reference, twice, on the development prompt, with the kernels of packet 32
and a Python controller. The reference is a median over twelve prompts and two repeats;
a comparable sealed figure needs the same suite (packet 38's suite window, with oracles
for all twelve prompts) and will differ by prompt, since the guess rate ran from 67% to
84% across the four prompts measured on CPU.

**Stops on the way (none was a device problem; each has an evidence folder):** a build
receipt missing two keys the inherited K1 gate reads
([evidence](../evidence/20261012-k1a-missing-build-receipt-keys/README.md)); K2 lost to
the full disk ([evidence](../evidence/20261012-k2-disk-full/README.md)); a race in the
KD wrapper's memory watch
([evidence](../evidence/20261012-kd-status-race/README.md)).

**Next gains visible in these receipts:** the kernels of packet 37 shorten each half
from about 23 to about 20.7 ms; the draft's output head gets the faster dense kernel
(1.9 → 1.4 ms); cancelling a wrong half as soon as the miss is known; moving the draft
to the first card with a second copy of the head and rebalancing layers hides the draft
time ((T+m)/2 per right guess instead of T/2+m); a native controller removes 1–2 ms per
token.

**Where the draft's time goes** ([W2mc](w2mc-r36e/rank1/class-times.json), per-class GPU
time on the second card, diagnostic): 3.3 ms of GPU time per guess, 4.3 ms of wall time.
The output head takes 1.68 ms, the draft's argmax 0.31 ms (it still uses the old
kernel; the target's takes 0.02 ms), QSA attention 0.20, the query/gate projection 0.12,
routed experts 0.15, route 0.07, the merge projections 0.09, the rest of the layer about
0.4 ms. About 1 ms of each guess is not kernel time: the second card's process waits for
the guess and publishes it before it issues its half. Issuing the half right behind the
draft's kernels and reading the guess when it arrives would remove that wait; the newer
dense kernel and the newer argmax take another 0.6 ms off.
