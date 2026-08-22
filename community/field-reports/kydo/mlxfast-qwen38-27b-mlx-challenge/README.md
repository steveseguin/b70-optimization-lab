# mlx.fast Qwen3.8-27B Apple Silicon challenge — field report collection

Evidence level: `community-reported`

Contributor/source: Kydo (`@0xkydo`), X post relayed by the maintainer on
2026-08-21 (post timestamped ~4h before intake). Original post URL not
captured; content preserved from the relayed copy.

Reference-lab reproduction: none, and none is possible on this lab's charter —
the platform is Apple Silicon (MLX on an M5 Max verifier), not Arc Pro B70.
This collection exists because the challenge's scoring design, gates, and
speculative-decoding techniques transfer to the B70/XPU lanes. It is
informational only; do not treat any number here as a B70 expectation.

## Report index

| Report | Contents |
| --- | --- |
| [challenge-results-2026-08-21.md](challenge-results-2026-08-21.md) | Headline numbers, scoring/gate design, technique summary, maintainer notes on B70 transferability |

## Lab-authored synthesis

The B70-focused ideas mined from this source (and from the SergiioB cookbook
hub) live in
[`notes/2026-08-21-b70-optimization-ideas-from-community-sources.md`](../../../../notes/2026-08-21-b70-optimization-ideas-from-community-sources.md).
