# Packet 107 QSA specialised layer: micro loses, closed (2026-10-18)

Lane B, card 2, two fresh processes (`packet107-micro-B-1` 07:49–07:50 UTC, `-B-2` 07:52–07:53), binary `ffd79f4e…`, 50 AB/BA pairs per context (10 warm-up, 40 measured), all 644 state comparisons equal (exact output identity `ace72452…`). No fault (count 2).

| Context | Current median µs | Specialised median µs | Paired saving µs (B-1 / B-2) |
| ---: | ---: | ---: | ---: |
| 128 | 519.9 / 519.2 | 527.2 / 526.8 | **−8.0 / −8.5** |
| 4096 | 1048.0 / 1047.7 | 1080.2 / 1078.6 | **−33.2 / −33.0** |

The integration gate was ≥ +80 µs in each process at 128 tokens. The specialised QSA layer is slower; the arm is **closed** (GDN was already closed on the CPU because Intel changes a NaN payload). Same launch count (31) in both modes, so specialisation did not remove submissions.

Useful by-product, one complete QSA layer at 128 context (current mode, µs): qsa.qgate 97.2, expsgate 59.5, qsa.attention 52.3, expsdown 50.5, attention 45.3, hc.a.gate 22.7, hc.f.gate 22.3, small.ffn.q6 19.2, route 18.8, qsa.select 16.5, ffn.combine 11.8, shexpdown 11.5. `qsa.qgate` is the largest single class in a QSA layer and is worth a byte/roofline check.

Evidence: `experiments/own-xpu-runtime/stage2/packet107-specialised-layers/evidence/micro-B-{1,2}/native/iterations.jsonl`.
