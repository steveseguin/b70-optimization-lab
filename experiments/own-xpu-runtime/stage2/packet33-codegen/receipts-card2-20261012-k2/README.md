# Packet 33 candidates timed on card 2 (2026-10-12 02:05:50–02:06:03 UTC): expert down finally has a winner

K0 (01:45 UTC) and K2 passed; every candidate is byte-equal to the runtime's incumbent
on the card; clean kernel log. Medians of 200 repetitions, GPU event time per launch
group, rotated full-size buffers for the heavy classes ([table](k2-table.txt),
[summary](summary.json)).

| Class | Runtime R5 | Best before this packet | Packet 33 candidate | Result |
| --- | ---: | ---: | ---: | --- |
| Routed expert down (IQ4_NL) | 127.4 µs | 123.4 (`p29.down.wg32`) | **90.2** (`p33.down.select`); 101.3 (`p33.down.bank`) | first real gain for this class: 1.8 ms per token |
| gdn.qkv, Q6 / Q8 | 99.2 / 96.7 | 75.2 / 72.1 (`p28.dense.wg32`) | **62.3 / 56.9** (`p33.dense.segment`) | another 13–15 µs per launch |
| Routed expert gate/up, IQ2 / IQ3 | 175.9 / 175.3 | 82.5 / 84.2 (`p28.paired.wg32`) | 81.5 / 82.4 (`p33.gate.restrict`) | equal within noise |
| QSA attention | — | 175 (packet 18, earlier K2) | 159.3 (`p33.qsa.shape`; 189.6 for the round-2 form it specialises) | small gain |
| qsa.k | 10.0 | — | 8.3 | small |
| Route | 66.9 | — | 77.4 (`p33.route.rank4`) | slower, not adopted |

The study's cost model did not predict these (it expected `down.bank` at 63 µs to beat
`down.select` at 84; measured 101 and 90). The assembly reading was still what produced
the candidates. `p33.dense.segment` was only timed on gdn.qkv and qsa.k here; the other
dense classes (gdn.z, qsa.qgate, attention projection, logits, HC gates) use the same
kernel body and should be timed and adopted in the next integration.

The first K2 attempt stopped in the wrapper before launch (a path object in the
recorded command, [evidence](../evidence/20261012-k2-wrapper-posixpath/README.md)).
