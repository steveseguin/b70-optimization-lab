# Own runtime packet 51: second exact-order kernel round on card 0 (2026-10-17)

Windows `p51-a`, card 0, boot `2cba7160`; no new fault lines.

**E1, E2: passed.** Byte-identical outputs and fresh processes.

**T1, T2: passed.** Integration candidate: ordinary GDN, the **bar met** (≥40 µs per ordinary M=1 layer).

| Layer (owner 1) | Current (µs) | Candidate (µs) | Saved |
|---|---:|---:|---:|
| Ordinary GDN, M=1 | 629.2 | 584.1 | **45.2** |
| Ordinary GDN, M=2 | 1259.0 | 1169.1 | 90.8 |
| QSA (non-attention parts), M=1 | 3141.3 | 3100.8 | 39.4 |
| QSA, M=2 | 6280.6 | 6201.9 | 80.2 |

The current-side baselines already include the p48b expsdown kernel; QSA attention here is the old kernel, since p47 split32 is integrated separately.

**Winning classes (both owners):**

- route 43.3 → 24.6 µs (1.76x);
- hc.a.gate / hc.f.gate 1.26-1.28x;
- hc.a.low / hc.f.low 1.21-1.27x;
- attention output/combine 57.6 → 45.8 (1.26x).

**No change:** expsgate (IQ2_S) 1.00x, gdn.qkv 1.01x, hc inject 0.98-1.02x.

**Cumulative per ordinary layer, M=1:** 665 µs (packet 46 baseline) → 617 (p48b) → about 584 (p51) on these classes. QSA attention is cut 5.3-8.2x by p47 split32 on top.

**Next:** packet 49c = packet 49b + the p51 route/HC/attention kernels. It keeps the same arithmetic identity and the same packet 49 oracle.

Evidence: `experiments/own-xpu-runtime/stage2/packet51-round2/evidence-copy/` (compact receipts; the full ignored `evidence/` tree is 34 MB on disk).
