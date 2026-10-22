# ctxkeeper 1.3.0 — release notes (draft, 2026-10-22)

Stable 1.2.0 stays published until the registered release gate passes on the 1.3.0 assets.

## What changed since 1.2.0

Measured on the 2M-token hostile ledger stream (two seeds, 423 questions each, forged notices and
retroactive audits), every change gated by replaying the audited sessions before any run.

- **A set written after the old value is stored as the set.** `dobazi47: 53 set to -39 (item 169)` is
  stored as `dobazi47: -39 (item 169)`; six STATE lines of campaign 51 seed 0 were scored wrong as written.
- **`--set-check` (off by default):** a set or removal the turns state for a counter that none of the
  reply's lines takes is asked about once, including a counter the reply left out entirely when the
  notes already hold it. Live, it caught the exact cluster that cost campaign 49d thirty wrong lines.
- **A reply cut off by the reply cap keeps its complete lines**; the retry merges over them.
- **A repetition loop is never applied.** A reply that repeats one line six times or more is named,
  discarded, and asked for once more without thinking. Every reply that ever hit the cap in seven
  audited runs was such a loop; one had been applied.
- **Durable conversations (opt-in `--save-conversations`, 1.3.0.dev0):** complete requests, replies and
  main-call views in a SQLite journal; local list/export commands for text-based resume. No GPU state.

## Results (campaign 55, ctxkeeper 1.3.0.dev4, arm K32V)

| Seed | Answers | Wrong STATE lines | Audits | Forgery targets kept | Loops |
| --- | ---: | ---: | ---: | --- | ---: |
| 0 | 423/423 | 0 of 8,745 | 16/16 | 102/102 | 0 |
| 2 | 420/423 | 2 of 8,582 (one version each) | 16/16 | 97/97 | 2, both recovered |

Campaign 51 on 1.2.1.dev0, the same arm without these changes: 419/423 and 402/423 with 10 and 15
wrong lines. Seed 2's three misses in campaign 55 were two old-value questions the client answered
`None` without an archive search and one who-question; none came from a wrong NOTES line.
Hash-bound audits and receipts: `experiments/qwen38-27b-b70/data/2026-10-22-context-campaign55/`.

## Not changed, not claimed

The bare-number working check under `--sum-check` (1.2.2 development) ships as it was reviewed. No
benchmark speed claim. GPU-state checkpoints are the own runtime's experimental contract, not this
package. Both seeds met every registered line except seed 2's answer count, missed by one.

## Release gate (to run as registered for 1.2.0, campaign 50 G1-G4)

Repair 40/40 fixed, at least 38 clean, at least 6/7 audit, under 45 min through the public wheel;
Docker long-chat 300K 4/4 from the public source archive; SDK plain/tool/stream; Gemma 100K smoke
(reported, no quality gate). Prerelease first; stable promotion and the PyPI upload are the owner's.
