# Packet154 result: rank 0's reply wait is rank 1's draft (lane B, one-load split)

The run used lane B (cards 2+3). The smoke `packet154-split-smoke-B` ran 02:03:50–02:07:33 UTC. The v5 split `packet154-split-bracket-B` ran 02:09:08–02:16:39 UTC on 2026-10-19. All views were 13/13 exact, draft proposals were identical, control drift was 0.062%, and there were no GPU faults (count 2). This is diagnostic evidence only; it makes no speed claim.

## Smoke attribution: rank-1 activity during rank 0's waits

Measured per emitted interval over 756 intervals:

| Rank 0 wait | ms/interval |
| --- | ---: |
| Total wait on rank 1 | **1.546** |
| … overlapping rank-1 **draft** | **1.227** |
| … B half | 0.171 |
| … unassigned | 0.074 |
| … transport | 0.051 |
| … merge compute | 0.020 |

By op, op 9 (the draft/guess wait) is 1.245 ms and op 1 (the half reply) is 0.298 ms.

## v5 split: rank-1 host scopes, control medians in ms/cycle

| Scope | ms/cycle |
| --- | ---: |
| b_issue | 11.345 |
| hidden_export_completion | 8.873 |
| wait_rank0_command | 2.236 |
| b_completion | 1.612 |
| **draft_issue** | **1.571** |
| target_tail_issue | 0.065 |
| b_import | 0.058 |
| prefix export/pack, merge import, publications | < 0.03 each |

`remote_reply_wait` is **1.573 ms/cycle**.

- **Analyzer decision:** "packet152 draft brief: confirmed draft host issue/completion/publication". Nothing is removable by observation alone.
- **Caveats:** host intervals include queue and polling delay, a pending draft is not GPU compute, and medians are not additive.

## Decision

The draft on rank 1 sits on rank 0's critical path (≈ 1.2–1.6 ms per cycle). Packet147 needs ≈ 0.423 ms/hit of net draft saving for +2%. This is the measured recoverable wait that packet126's DO-NOT-REPEAT asked for.

**Codex p156** (launched 02:08 UTC) builds p152's draft_wait design: hidden-only draft work in rank 1's suffix slack, with proposals for both lanes.

Whole-graph replay is not reopened: packet34 measured it neutral.

Evidence:
- `experiments/own-xpu-runtime/stage2/packet154-rank1-split/v5/evidence/device-p154c-split-smoke-B/bracket-summary.json`
- `experiments/own-xpu-runtime/stage2/packet154-rank1-split/v5/evidence/device-p154c-split-v5-B/bracket-summary.json`
