# Packet 37 on cards 2+3 (2026-10-12 04:20 – 05:08 UTC): pipeline runtime with the new kernels, 21.50 tok/s sequential, exact

Two rank processes (one per card), packet 35's prepared host path, packet 33's kernels,
fixed K2 fusion rule. K0, K1a, K1b, K2 and W0p passed (run alongside packet 36's
windows on cards 0+1); W2s ran alone, pinned to the reserved cores. Clean kernel log.

**W2s (sequential generation, draft none): 64/64 tokens and 384/384 layers equal to the
v2 oracle; 21.50 tok/s** (46.5 ms mean per token, 42.3 ms median; the first eight
generated tokens also retain 48 layer fixtures each and are slower). The two halves take
20.7 + 20.7 ms of host-observed time ([receipt](w2s-r37/receipt.json)); packet 32 with
the previous kernels: 23.8 + 23.4 ms and 19.47 tok/s.

**What K2 selected on card 2** ([selection](k2-r37/dispatch-measured.json), medians of
200, rotated full-size buffers for the heavy classes, µs per launch group):

| Class | Before (packet 29 selection) | Selected now |
| --- | ---: | ---: |
| routed expert down | 127.7 | **90.4** (`p33.down.select`) |
| gdn.qkv, Q6 / Q8 | 75.3 / 72.5 | 62.1 / 56.9 (`p33.dense.segment`) |
| gdn.z, Q6 / Q8 | 49.0 / 46.5 | 39.1 / 36.1 |
| qsa.qgate | 90.5 | 74.4 |
| output head (logits) | 1,892 | 1,410 |
| HC gates | 20.9 | 15.6 |
| HC inject | 15.4 | 8.1 |
| shared expert down | 11.5 | 8.2 |
| attention projection | 52.3 | 52.3 (the new form measured 49.1, under the 10% threshold) |
| routed expert gate/up, IQ2 / IQ3 | 83.1 / 86.0 | unchanged (`p28.paired.wg32`; `p33.gate.restrict` 82.0 / 85.7) |
| QSA attention | 174.3 | unchanged (packet 18; `p33.qsa.shape` 159.4 is fixed to capacity 128 and the model runs at 256) |
| small merged GEMVs | | fusions kept for the router/shared-expert group and GDN a+b; HC low+inject now cheaper as two launches (12.7 + 8.1 against 26.6 for the fusion) |

About 4 ms of GPU time per token less than packet 29's selection.

The all-right-guess diagnostic (W2d) for this runtime is queued behind packet 36's
windows.
