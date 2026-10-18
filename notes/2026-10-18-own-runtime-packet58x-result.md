# Packet58x result: 21.55 GB device expert cache, +4.1% exact on the one-card overlap line

One-load bracket `packet58x-v5-d-A`, lane A, card 0, whole host, 20:12–20:26 UTC October 18 (boot 2cba7160, GPU fault count 2). Smoke `packet58x-smoke-d-A` passed first (20:03–20:10). Codex units other than disk jobs kept running during the bracket (review 30, `thaw-critical`). Evidence: `stage2/packet58x-cache-capacity/evidence/card0-capacity-d/max/WSCREEN/summary.json`.

| View | Device cache usage | tok/s |
| --- | --- | ---: |
| A0 | 18 GB (first view; empty cache, warm-up per the p58wb rule) | 23.110 |
| B0 | max 21.55 GB | 29.569 |
| A1 | 18 GB | 28.157 |
| B1 | max | 29.364 |
| A2 | 18 GB | 28.200 |

- All five views are exact against packet49 (same oracle completion hash).
- Strict gain (slower max view / faster warm control) is **+4.13%**; warm-control drift is 0.15%.
- The replay had projected +2.26%. The measured gain is larger, consistent with more fills and zero-copy misses avoided once the overlapped maintenance is in place.
- The admitted capacity keeps the 1.5 GB device reserve and the measured host bound (packet58x ADMISSION.md).

Path to this run: three earlier attempts failed on packaging, not on the device.
- smoke-a refused at its build gate (a sibling pin to packet58w).
- smoke-c stopped on a KiB-only DRM fdinfo parser (fixed by p58xd).
- smoke-d's first try refused on the packet-local latch left by smoke-c (latch archived; the refused output was set aside as `smoke-refused-latch-20261018T200309Z`).

Decision: this clears the +2% record-chain rule alone (expected about 28.04 × 1.041 ≈ 29.2 tok/s). Codex p58z prepares a vendored one-card record chain (21.55 GB cache, overlap, tile16). Codex is frozen from WS through WS128 per review 29.
