# Own runtime packet 46: device result (2026-10-17, card 0) — fusion neutral; QSA attention is the big sink

Windows `p46-a` on boot `2cba7160`, card 0. The fault review covered the 2 known lines from 01:09; no new fault lines appeared.

| Window | Result |
|---|---|
| E1, E2 exactness (fresh processes) | **passed**: the specialized GDN/QSA compositions are byte-identical in every intermediate and in state |
| T1, T2 per-class GPU timing (200 pairs each, 4K populated attention, M=1) | ran cleanly; **bar not met** |

| Layer | Current (µs) | Specialized (µs) | Saved | Bar (80 µs) |
|---|---:|---:|---:|---|
| Ordinary GDN, owner 1 / owner 2 | 670.9 / 665.7 | 675.1 / 669.1 | −3.9 / −4.2 | no |
| QSA, owner 1 / owner 2 | 3181.9 / 3181.8 | 3175.3 / 3175.3 | 7.4 / 3.9 | no |

**Fusion of launches is not the lever.** GPU time lives inside the kernels:

- `gdn.qkv` + `gdn.z` 139.8 µs became `p46.gdn_projections` 134.1;
- the hyper-connection norms rose from 19.3 to 35.7 µs once fused;
- gate/mix were unchanged at 57.5 µs.

**Where a 4K-context decode layer spends GPU time (current):**

- **QSA layer: `qsa.attention` 2,370 µs of 3,182** (75%), `qsa.select` 180, `qsa.qgate` 113. The attention reads a few MB of selected KV per token, so it runs roughly 100x above its memory floor. With 12 QSA layers, this dominates decode once the context passes a few thousand tokens.
- **Ordinary GDN layer (671 µs):**
  - experts: gate/up 81.9, down 91.9;
  - GDN projections: qkv 100.1, z 39.7;
  - attention: 57.6;
  - router: 43.4;
  - recurrence: 35.9;
  - hyper-connection set: about 120;
  - small FFN (Q6): 27.8.
  - The expert GEMVs run at roughly 70-150 GB/s effective, against about 550 GB/s available.

**Next levers, ranked:**

1. **QSA decode attention efficiency.** Use a split/parallel reduction over the selected tokens. A changed reduction tree requires a matching CPU-oracle update (the IQ3 line is lossless against its own CPU reference, as in the October 11 oracle rebase) and full-suite requalification.
2. **GEMV bandwidth for IQ3/Q6 experts and projections.** Prefer layouts and loads that keep each output's accumulation order, so existing oracles stay valid.

Evidence: `experiments/own-xpu-runtime/stage2/packet46-specialized/evidence/p46-a-{e1,e2,t1,t2}/`, `p46-a-summary.json`.
