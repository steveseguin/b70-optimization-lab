# Post-seal note (2026-10-19, written after READY `2eb804e35`)

Packet175's D2 micro ran on lane B while this packet was being prepared. It closed
D2 (`f8aebb924`): weighted dense B/A was 1.4386 with the warm-ahead time included.
The GEMV-only time improved, by about 15% on L0 and 5.5% on L3, but the warm kernels
cost about 0.2 ms per row.

The same run also shows that this harness works on device:

* every timed pass passed its oracle check;
* the A-arm dense time is 0.300 ms/row for L0 and 0.555 ms/row for L3.

Consequences for packet175b:

* **Combined candidate.** The sealed analyzer, README and note say the combined
  bundle-9 candidate is "packet153 + D2 + D1". With D2 closed, an eligible D1 result
  means a combined candidate of **packet153 static descriptors + D1** only. D1 is
  still never built alone.
* **No other changes.** The decision rule (B/A ≤ 0.97) and all sealed files are
  unchanged. This file is new and is not part of the sealed closure.
