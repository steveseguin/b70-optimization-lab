# Packet 27, sealed chain on cards 0+1 (2026-10-11 23:41 – 2026-10-12 00:11 UTC): 19.63 tok/s, exact

K0, K1a, K1b (two fresh owners, every new kernel against the reference core), K2
(per-class timing with selection), W0 (two-card canary) and W2m (two-card decode with
the selection K2 measured) all passed through the packet's own wrapper; clean kernel log.

**W2m: 64/64 tokens and 384/384 layer fixtures equal to the v2 oracle; 19.63 tok/s**
(50.2 ms per token: 11.9 ms host issuing, 37.8 ms waiting on the cards; 1,898 launches).

What K2 selected over the packet 26 line ([table](k2-table.txt), µs per launch group):
gdn.recurrence 53.9 → 34.9, qsa.select 67.4 → 16.0, argmax 294 → 20.7; merged small
GEMV groups: HC low+inject 33.9 → 16.0, GDN a+b 14.6 → 4.6, router + shared expert
gate/up + scalar gate 88.2 → 35.3; and the packet 25 `rows4` variants for gdn.qkv,
gdn.z, qsa.qgate, logits, ple.key and hc.low. Not adopted (not faster): the new route,
QSA attention, gdn.norm, qsa.prepare, qsa.pool.

Same-day progression of the exact two-card decode: 3.15 → 12.08 → 17.85 → 19.63 tok/s.
Reference 28.49.
