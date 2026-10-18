# Packet58t result: resident lookup tables do not help (one-card)

Lane A, card 0, one whole-host window `packet58t-resident-A`, 15:21–15:35 UTC
October 18 (boot 2cba7160, GPU fault count still 2). Packet: 
[packet58t-resident-lookups](../experiments/own-xpu-runtime/stage2/packet58t-resident-lookups/ANALYSIS.md).
Evidence: `stage2/packet58t-resident-lookups/evidence/card0-resident-a/resident/`
(`K1b/summary.json`, `WSCREEN/summary.json`).

The candidate copies the two host-read lookup tensors (Q6_K `token_embd`,
IQ4_NL `per_layer_token_embd`, 29.3 GB) into anonymous memory at load. It
keeps the tile16 one-card engine otherwise unchanged.

| View | Label | tok/s (primary metric) |
| --- | --- | ---: |
| tile16 control | A0 | 21.412 (first view; cold) |
| resident lookups | B0 | 26.092 |
| tile16 control | A1 | 26.134 |

- All three views are exact against packet49 (same oracle completion
  SHA-256 `38ef0aed…`). K1b passed (24 checks).
- Candidate vs best control: **−0.162%** (required +0.5%). Control drift is
  22.05% because the first control ran cold; that fails the 3% drift gate,
  but the warm control alone already beats the candidate.
- Verdict: **loss / no gain, closed.** Host page faults on the lookup path
  are not what limits one-card decode once the process is warm. Packet58q's
  variance theory doesn't hold up as a throughput lever. The record stays
  **26.228599** (`cmvdukc200064rf01lqsql9x8`).

Next: no one-card lever is queued. Packet58h already closed one-card MTP
(host RAM and projected rate). One-card work waits for a new mechanism.
The 2-card lane continues with packet131b (lane B grid running) and
packet136/137.
