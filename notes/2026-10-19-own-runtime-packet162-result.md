# Packet162 result: the exact 11-bit IQ2 decoder is 4.8× slower on the device; the last two-card in-layer pool closes

One-card diagnostic micro `packet162b-enum11-diagnostic-B`, lane B, physical card 2 (PCI 0000:43:00.0), 04:54:46–04:54:54 UTC on 2026-10-19. It ran the production gate/up kernel against the 11-bit grid candidate at real bundle-8 shapes. No GPU faults (count 2); drained.

| Shape | Fixture | Production median | Candidate median | Ratio |
| --- | --- | ---: | ---: | ---: |
| layer0 | 0 | 48.3 µs | 232.6 µs | 4.81× |
| layer0 | 1 | 48.3 µs | 231.7 µs | 4.79× |
| layer24 | 0 | — | — | 4.83× |
| layer24 | 1 | — | — | 4.82× |

- Output bytes were equal on the device for finite and invalid/NaN fixtures. The CPU auxiliary NaN differences from packet162 did not appear in device output.
- The gate was ≤ 0.85×. **Closed.**
- With packet156 (draft slack), packet158 (draft roofline), packet160 (structural, ≤ 2.2%), packet161 (early argmax, ≤ 2.24%) and now packet162 closed, no measured single-stream decode lever above 3% remains on the two-card bundle-8 architecture.
- Small exact gains remain (packet153 static snapshot +0.35%), and the bundle-9 record chain (packet155) is being prepared under the idle-lane rule.
- Per AGENTS.md rule 4, the next two-card work widens the target rather than stopping.

Evidence: `experiments/own-xpu-runtime/stage2/packet162-iq2-lookup/evidence/enum11-diagnostic-B1/analysis.json`.
