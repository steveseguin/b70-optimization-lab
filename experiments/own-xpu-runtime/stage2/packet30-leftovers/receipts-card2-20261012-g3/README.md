# Packet 30 candidates timed on card 2 (2026-10-12 02:41 UTC): one large winner, most others slower

K0 and G3 passed after the wrapper fix (library path forwarding; the first attempt saw
no device, [evidence](../evidence/20261012-k0-no-devices-missing-library-path/README.md)).
Two fresh owners, 200 repetitions each, every candidate byte-equal to its incumbent on
the card; clean kernel log. Medians, µs of GPU time per launch group
([full table](timing-table.md)).

| Class | Incumbent | Best candidate | Reading |
| --- | ---: | ---: | --- |
| **QSA attention** | 347 (this fixture; 265 in the model at the development prompt) | **117** (`p30.attention.sg32`, three launches); 157 (`score_softmax`, two launches) | the largest gain of this packet, up to about 1.8 ms per token; the fixture's context shape differs from the model run, so it must be confirmed at model shape before adoption (packet 33's `qsa.shape` measured 159) |
| small.ffn (Q6 layers) | 29.7 | 26.3 (`p30.small.rows4`) | −11%, 0.16 ms per token |
| HC gates | 20.6 | 19.3 | −6% |
| shared expert down | 11.1 | 10.5 | −5% |
| small.ffn (Q8 layer), HC mixes | 23.5; 9.6 | 24.3; 9.7 | equal |
| Route | 67–87 | 89 (two launches, 16 groups); 635–748 for the single-group forms | slower: every attempt to cut launches by serialising work inside a kernel loses |
| small.hc | 15.0 | 37.1 | slower |
| combine + norm in one launch | 17.1 (three launches) | 143–225 | far slower |
| HC norms in one launch | 8.6 (two launches) | 65–99 | far slower |

Lesson repeated from packets 21–27: on this GPU a launch costs 3–5 µs, and a kernel that
replaces several parallel launches by one launch with serial reductions inside is slower
by an order of magnitude. Merging launches only pays when the merged kernel keeps every
lane busy (the small merged GEMVs of packet 27, the paired expert kernel of packet 28).
