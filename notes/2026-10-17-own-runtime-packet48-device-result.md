# Own runtime packet 48: order-preserving GEMV on card 0 (2026-10-17)

Windows `p48-d`, card 0 (PCI `0000:23:00.0`), boot `2cba7160`; no new fault lines.

- `p48-a-e1` passed its 126 device byte comparisons, but the window failed on the inherited packet34 memory sensor. At exit that sensor read the native child's status while it was a zombie (no `RssAnon`), and it latched an "uncertain owner" fault for the boot.
- The sensor fix is `f8fd9dd35`: zombie tasks are skipped, and live tasks without `RssAnon` still refuse.
- The false latch was reviewed and archived as `evidence/p48-a-e1/latch-archived-reviewed.json`. Windows `p48-c` refused on that latch before it was archived.

| Window | Result |
|---|---|
| E1, E2 | **passed**: new kernels byte-identical to the current ones; accumulation order preserved, so existing oracles hold |
| T1, T2 | passed; **performance bar met** in both owners. Ordinary-GDN saving 51.98 / 51.09 µs per layer (bar 40 µs). Expert speedup 1.276x / 1.266x (bar 1.5x not met; the OR-bar met via the per-layer saving) |

Old µs → new µs (owner 1; owner 2 within 1%):

| Class | M=1 | M=2 |
|---|---|---|
| expsdown | 93.5 → 56.5 (1.66x) | 184.4 → 115.2 (1.60x) |
| expsgate.iq2 | 106.9 → 100.9 (1.06x) | 159.4 → 147.8 (1.08x) |
| expsgate.iq3 | 87.2 → 86.7 (1.01x) | 170.9 → 165.8 (1.03x) |
| gdn.qkv.q6 | 63.5 → 57.7 (1.10x) | 115.3 → 60.1 (1.92x) |
| gdn.qkv.q8 | 53.5 → 48.1 (1.11x) | 98.0 → 56.6 (1.73x) |
| gdn.z.q6 | 31.9 → 30.1 | 55.6 → 37.4 (1.49x) |
| gdn.z.q8 | 29.5 → 27.9 | 53.1 → 35.1 (1.51x) |

**Not yet integration-eligible.** The preregistered sanity check `current_primary_controls_within_15pct` is **false**: this bench's control timings differ from packet 46's production per-class timings by more than 15% (for example, expert gate/up is 107 µs here against 82 µs in p46). The bench shapes and mixes must be reconciled with the production kernels before the gain is trusted. Integration then follows with the packet-47 split32 QSA.

Evidence: `experiments/own-xpu-runtime/stage2/packet48-gemv/evidence/p48-d-{e1,e2,t1,t2}/`, `p48-d-summary.json`.
