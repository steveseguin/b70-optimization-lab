# Packet 39 epilogue fusions timed on card 3 (2026-10-12 04:14 UTC): all exact, about 1.2 ms per token

Twelve cases, 200 repetitions per arm, rotated full-size buffers above 8 MB, 84 byte
identity checks, every fused kernel byte-equal to the unfused chain on the card; clean
kernel log. Medians of the summed GPU time of one launch group (the whole chain).

| Fusion | Unfused chain | Fused | Per group | Groups per token | Per token |
| --- | ---: | ---: | ---: | ---: | ---: |
| routed expert gate/up + both status checks, IQ2 / IQ3 | 71.3 / 76.2 µs | 64.6 / 69.9 | −6.7 / −6.4 | 48 | −0.31 ms |
| routed expert gate/up + activation, IQ2 / IQ3 (alternative to the line above; the combination of both was rejected on its assembly) | 74.3 / 80.4 | 70.5 / 76.1 | −3.7 / −4.3 | 48 | (−0.19) |
| routed expert down + status check | 96.9 | 94.0 | −2.9 | 48 | −0.14 |
| attention output projection + combine | 63.6 | 59.2 | −4.5 | 48 | −0.22 |
| HC low + activation | 19.1 | 17.2 | −1.9 | 96 | −0.18 |
| shared expert up + activation, Q6 / Q8 | 16.0 / 18.5 | 13.5 / 14.7 | −2.5 / −3.9 | 48 | −0.12 |
| shared expert down + blend/combine | 27.1 | 24.7 | −2.3 | 48 | −0.11 |
| gdn.qkv + convolution, Q6 / Q8 | 69.3 / 64.1 | 68.7 / 64.4 | −0.6 / +0.3 | 36 | none |

Each removed launch is worth 2–3.5 µs, the card's cost of dispatching one more kernel.
Folding an element-wise step into the store of the GEMV that feeds it is exact and
free of the serial-work penalty, but the total is about 1.2 ms of the 41 ms per token.
Worth carrying into the integrated runtime once, not worth another round.

The first G4 attempt stopped at its sixth case on a host-side check
([evidence](../evidence/20261012-g4-row-stride-check/README.md)); its five completed
cases agree with this run within 0.5 µs.
