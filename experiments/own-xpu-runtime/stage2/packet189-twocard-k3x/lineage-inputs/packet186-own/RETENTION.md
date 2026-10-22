# Packet186 retention

**Tracked:**

* **Sources.** The identity-rewritten copy of packet185's harness (`lineage/packet186-copy.json`) and the packet186 V3
  deltas (`v5/v3-native.patch` records every native change against packet185).
* **`analysis/`.** The measured V3 pricing (`price_v3_measured.py`, `price-v3-measured.json`) and its read-only input
  `p185-intervals.json.gz` (147 KB). That file holds packet185's 5 x 12 x 99 measured intervals plus rank-0 scopes;
  every source receipt is recorded with its sha256.
* **CPU gate receipts and logs** under `v5/evidence/`:
  * the hashed full-shape archives `shape-*.tar.gz`;
  * the V3 state transcripts `v3-state-engine-*.txt.gz`;
  * `compile-poll.json`.
* **`lineage-inputs/`:**
  * `packet185-own/`: packet185's certification, proposal, window lineage, analysis (the lever synthesis), and the
    small receipts this packet cites. These are its CPU gate receipts and, for each of the five device views,
    `bracket-summary.json`, `window.json`, `identity.json` and the view `summary.json`/`identity.json`.
  * `packet183-own/`, `packet153-own/`, `decision-fixtures/`: inherited unchanged. The s186 rule tests read the real
    packet183/185 summaries and streams there.

**Ignored and local** (`/v5/build/`, `/build/`):

* the compiled engines and objects (`gnu-host/`, `device/`);
* the 78 `inherited/` links to the pinned packet103/136 objects;
* the CPU fixtures (full-shape, controller mocks, V3 state engines).

To recreate them, run `nice -n 19 taskset -c 8-15,24-31 python3 -B v5/p186_v5_build_engine.py`. It needs the compiler
and polls the window unit first. Then run `v5/qualify_cpu.py --start full-shape`. The V3 state gate deletes its raw
miniature request trees after writing `v3-state.json`.

The device output directories named in the proposal (`v5/evidence/device-row{0..3}-*-B-p186`) must stay fresh.
