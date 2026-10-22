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

## Release gate (campaign 56, 2026-10-22, passed on these public prerelease assets)

| Gate | Result |
| --- | --- |
| G1 freeagent + `ctxkeeper --recipe qwen`, 40 repair tickets, through the public wheel | 40/40 fixed, 40/40 clean, 7/7 audit, 14 min 45 s (bar: 40/40, at least 38, at least 6, under 45 min) |
| G2 300,000-token chat through the Docker image built from the public source archive | 4/4 |
| G3 the README's OpenAI SDK snippet: plain, tool call, stream | all three |
| G4 Gemma 4 26B Q8, 100,000-token smoke (reported, no quality gate) | 4/4 |

Kernel log clean; cards left empty. Receipts: `experiments/qwen38-27b-b70/data/2026-10-22-ctxkeeper-1.3.0-release-gate/`.
Stable promotion and the PyPI upload are the owner's.
