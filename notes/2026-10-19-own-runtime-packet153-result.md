# Packet153 result: static snapshot descriptors are exact but +0.35%, below the +0.5% bar

Lane B (cards 2+3), one-load v5 bracket `packet153-static-bracket-B-p153b`, 01:45:24–01:53:38 UTC on 2026-10-19. The smoke `packet153-static-smoke-B-p153b` (01:40–01:43) passed exact after p153b removed the 60 s data-proof wall deadline. The first smoke had failed only on that deadline: TTFT on a cold first prefill is 59.6 s.

| View | Choice | tok/s (class-balanced) | 13/13 exact |
| --- | --- | ---: | --- |
| 0 | production | 58.638 | yes |
| 1 | **static** | **58.874** | yes |
| 2 | production | 58.671 | yes |
| 3 | **static** | **58.878** | yes |
| 4 | production | 58.663 | yes |

- Control drift is 0.057%, and draft proposals are identical.
- Static beats the best control (58.671) by **+0.35%**, against the preregistered **+0.5%** winner bar. **Not a winner.**
- The bundle-9 record chain (packet155) is **not justified**. Its preparation (Codex p155r) was stopped, and the tracked files were restored to the committed `ready_for_device:false` marker.

**Interpretation:**
- Packet150 measured rank 0's `capture_snapshot` host scope at 0.743 ms/cycle.
- Removing the per-cycle descriptor build and upload saved about 0.06 ms per emitted interval (+0.35% of 17.0 ms).
- So most of that host time overlaps device work and is **not on the critical path**. Host-side scopes on rank 0 are not where the two-card interval is spent.
- The remaining large bucket is rank 0's 1.54 ms `remote_reply_wait` on rank 1. Packet154's rank-1 split (queued next on lane B) attributes it.

**Retained as a small exact component:** static descriptors could join a future composite bundle if other exact sub-bar gains accumulate to ≥ +2%. They are not adopted alone.

Evidence: `experiments/own-xpu-runtime/stage2/packet153-snapshot-host/v5/evidence/device-static-v5-B-p153b/bracket-summary.json`.
