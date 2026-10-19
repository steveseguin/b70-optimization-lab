# Packet165 one-card result: warm 512-token prefill 32.6–32.8 tok/s; decode 31.5–31.8 tok/s with the full strict-512 gate (two fresh loads)

Card 0, two whole-host fresh loads on the packet58aj identity (the 31.966820 record line, resident lookups, unchanged arithmetic):
- `packet165-p165c-one-card-full512-A-a` (07:24–07:33 UTC);
- `-A-b` (07:34–07:43 UTC).

Both used the native under `ionice -c3`, added by packet165c. No GPU faults (count 2).

| Run | 512-token prefill (warm runtime, cold prompt) | TTFT | Decode (primary, full 512 cap) | Full natural completion | Realistic gate | Oracle-covered tokens |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| a | **32.75 tok/s** | 15.633 s | 31.782 | 33.156 | passed | exact |
| b | **32.59 tok/s** | 15.708 s | 31.510 | 32.844 | passed | exact |

- The prefill definition is the same as the two-card packet165 note: 512 input tokens / request TTFT, after one warm-up request on a different prompt and a full reset, `cached_tokens=0`.
- Decode under the full 512 cap is 31.51–31.78 tok/s, against the 128-token-scope record 31.966820. This is not a new record; it is recorded as the first full-gate evidence for the one-card line.
- One-card prefill (32.7 tok/s) is the slowest published number on either line. With exact batching it has the most room to gain, and packet166's M=2 layer micro decides that.

Evidence: `experiments/own-xpu-runtime/stage2/packet165-warm-prefill/one-card/evidence/device-p165c-warm512-A-{a,b}/bracket-summary.json`.
