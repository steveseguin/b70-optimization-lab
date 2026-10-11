# Packet 25 G1 attempt a (card 0): stopped at an exceptional-input fixture (2026-10-11 20:23 UTC)

K0 passed. G1 stopped after 5 s, cleanly, at fixture `k256/special1/input3/split1`:
the CURRENT kernel on the card differs from the host reference at element 14. All 14
ordinary fixtures run before it passed for the current kernel and for all six expert
gate/up candidates (current == host, candidates == current). The failing fixture feeds
exceptional values (NaN, denormal or infinity). No timing rows were produced.

The model path never computes with non-finite values (the runtime raises its sticky
error on them), and the lane's exactness gates are on finite real-model values. The
G1 gate as written demands host/card bit equality of NaN encodings too, which stops the
whole timing run.
