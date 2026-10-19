# Packet163 two-card result: bundle 8 passes the full strict-512 realistic gate at 58.61–58.63 tok/s (two fresh loads)

Two fresh loads on lane B (cards 2+3), using the bundle-8 identity (packet136 engine, unchanged arithmetic):
- `packet163-two-card-full512-B-a`: 05:56–06:02 UTC;
- `packet163-two-card-full512-B-b`: 06:04–06:09 UTC.

No GPU faults (count 2).

| Run | Primary metric (median of class medians, 99 intervals after TTFT) | Full natural completion (512 cap) | Median TTFT | Realistic final gate |
| --- | ---: | ---: | ---: | --- |
| a | **58.610** | 55.686 | 896 ms | **passed** |
| b | **58.625** | 55.720 | 896 ms | **passed** |

- The two loads agree within 0.03%.
- Every oracle-covered token is exact: the packet49 CPU oracle covers the first **128** tokens, and tokens beyond that are determinism-checked across the two loads only, not oracle-exact.
- This is the first full strict-512 realistic-gate measurement of the IQ3 two-card line.
- It is **not a new record**: the 128-token-scope record is 58.798109, and 58.62 is the more complete measurement. It is recorded as evidence and not submitted.

**Prefill (512 tokens, one user):** reported 7.84/7.85 tok/s, with a TTFT of 65.3 s. That request ran **first** in each process, so it includes the cold first-request cost seen all night (≈ 60 s). The suite's warm median TTFT is 0.90 s for ~80-token prompts, which implies roughly 90 tok/s warm prefill. A warm re-measure (512-token prefill after a warm-up request) is the next step.

Either way, prefill runs one token at a time. Batched multi-token prefill is a large widened lever.

Evidence: `experiments/own-xpu-runtime/stage2/packet163-full-gate/two-card/evidence/device-full512-B-{a,b}/bracket-summary.json`.
