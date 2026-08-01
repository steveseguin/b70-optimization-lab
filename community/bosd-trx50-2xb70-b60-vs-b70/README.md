# Arc Pro B60 vs B70 — single-card head-to-head

**Contributor:** bosd · **Evidence:** B70 column `B70-tested`; **B60 column `community-reported`** (reference lab has no B60 — see [`STATUS.md`](STATUS.md)).
Full write-up: **https://github.com/bosd/trx50-arc-b70-benchmarks/blob/master/results/b60-vs-b70.md**

The returned-from-RMA Sparkle **B60 (G21, 24 GB)** dropped into the TRX50 alongside a **B70 (G31, 32 GB)**, same models, single card each. `llama-bench -p 512 -n 128`; W = GPU-only (`xe` card energy counter).

| Model | backend | B60 pp512 | B60 tg128 | B60 W | B70 pp512 | B70 tg128 | B70 W |
|---|---|---|---|---|---|---|---|
| Qwen3-4B-Q4 | SYCL | 2236 | **101.8** | 81 | 3280 | 115.7 | 144 |
| Qwen3-4B-Q4 | Vulkan | 1698 | 55.4 | 72 | 2390 | 79.9 | 138 |
| Qwen3.6-35B-A3B-Q4_0 | Vulkan | 908 | 37.3 | 60 | 1250 | 48.0 | 96 |
| Qwen3.6-35B-A3B-Q4_0 | SYCL | — | — | — | 980 | 71.8 | 77 |

## Takeaways

- **Generation: B60 ≈ 78–88% of a B70** (88% on the SYCL production path).
- **Prompt processing: B60 ≈ 68–73%** — the B70's extra Xe cores show on compute-bound prefill.
- **Power: B60 draws ~56–63% of a B70** → **1.2–1.6× more tokens/joule**.
- **VRAM: 24 GB (21.5 usable) vs 32 GB** — B60 fits a 20 GB MoE fine but has 8 GB less headroom.
- **B60 POSTs** (G21 has mature DP+HDMI GOP); the B70 (G31) gives no pre-OS video on this board, so the B60's slot can double as console **and** compute.

**Verdict:** the B60 is the **efficiency + console** card; the B70 is the **VRAM + prompt-throughput** card. Don't put a B60 in a `-sm layer` tensor-split with B70s (bottlenecks them; the 24/32 GB mismatch wastes the B70's VRAM). For a VRAM-bound big-model mission, expand with **uniform B70s**; the B60's efficiency edge pays off best on an always-on box.
