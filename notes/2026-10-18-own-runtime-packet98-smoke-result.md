# Packet 98 v5 one-load bracket: smoke result (2026-10-18 04:26–04:31 UTC, lane B)

`packet98-smoke-B`: shared wrapper `stage2/screen/v5-bracket`, packet 84's selection run against itself in one device-owner lifetime.

| Field | Value |
|---|---|
| model lifetimes / target loads / draft loads / teardowns | 1 / 1 / 1 / 1 |
| all 13 exact (both views) | yes |
| control drift | **0.14%** (limit 3%) |
| measured wall | **274 s** for 2 views |

**Comparison:**
- Two v4 screens of one selection take about 2 × 233 s plus a 90 s gap, about 556 s.
- v4 control drift tonight reached 1.0% (packet 97 decision `f1e5d7f47fc0fe54`, lane B: 55.076 / 55.652). That is larger than the gains being judged (0.3–0.9%).

**Next:** Codex packet 98b makes v5 brackets (A/B/A/B/A) the default for packet 97 composites, leave-one-outs and single-source screens, and teaches packet 97 readiness to accept v5 evidence. Views with a different load-time layout (for example `head-transpose`) still need v4.
