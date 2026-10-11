# Packet 26 with the measured kernel selection: 17.85 tok/s on two cards, exact (2026-10-11 22:16 UTC, cards 0+1)

The sealed packet 26 decode binary, run natively by the coordinator with the dispatch
table K2 measured on this boot (`a2-k2/run/dispatch-measured.json`). 64/64 tokens and
all captured layer fixtures equal to the v2 CPU oracle (the native program compares
them itself and stops at the first difference); clean kernel log.

| Configuration (two cards, R5 GEMV, wall-clock timing) | ms per token | tok/s | host issue | waiting on cards |
| --- | ---: | ---: | ---: | ---: |
| packet 18 as first sealed | 315.2 | 3.15 | — | — |
| packet 26 control: packet 18 kernels, fast host path | 81.6 | 12.08 | 10.4 | 70.6 |
| **packet 26, kernels selected by K2** | **55.4** | **17.85** | 11.3 | 43.8 |

Why this is a coordinator run and not the W2m window: K2's wrapper verdict is "failed"
because the timing harness's `qsa.pool` workload mismatched its fixture for both the
packet 18 kernel and the new one, which points at the harness; that class is excluded
and stays on the packet 18 kernel. Every class the table switches (route+gather, the
two combine+norm steps, gather, hc/final/PLE norms, argmax, streams, ple.add) passed K1
in two fresh owners and K2's own byte comparison. The sealed W2m follows once the
harness is repaired.

K2, GPU execution time per launch group on card 0 (µs, median of 200):
route+gather 286 → 67; attn.combine+norm and ffn.combine+norm 179 → 17; gather 82 → 23;
hc.combine_norm 65 → 18; norm 25 → 8; argmax 267 → 191. Not faster and left on the
packet 18 kernels: gdn.recurrence (53 versus 156), qsa.pool, qsa.prepare, gdn.norm,
qsa.select, qsa.attention.

## Fresh-process repeat on the other card pair (22:25 UTC, cards 2+3)

17.81 tok/s (55.6 ms per token: 11.7 ms host issue, 43.5 ms waiting on the cards),
exact against the oracle, and all 64 tokens and all 384 layer hashes identical to the
cards 0+1 run above (`repeat-cards23-run-c/`).
