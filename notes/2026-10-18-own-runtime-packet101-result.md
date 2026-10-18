# Packet 101 result: draft-attention geometry (packet 69's shelved view), both lanes (2026-10-18 04:49–05:24 UTC)

v4 screens on packet 97's base selection; all views 13/13 exact; acceptance unchanged (0.7874).

| Lane | Control 1 | draft_attention | Control 2 | Gain vs stronger control |
|---|---|---|---|---|
| A (record lane) | 55.579 | **55.756** | 55.601 | **+0.28%** |
| B | 55.617 | **55.807** | 55.507 | **+0.34%** |

- Hit cycle on A: 15.574 ms vs 15.664–15.673 ms (−0.09 ms; the draft sits on every hit's critical path).
- Packet 69's draft-HC view was already active in the base. Only the attention geometry was new.

**Qualified** as a composition source for the next bundle, together with packet 100 `down-tile16` if its screens confirm (microbenchmark kernel 0.695×). Packet 91 (route-fast + rec-both-plus) and packet 90 E1 are already in the pending packet 97 chain (decision `f1e5d7f47fc0fe54`; KD fix in progress, packet 97e).

## v5 native bracket (packet 98c, lane B, 05:49–05:58 UTC): one model load, five views, all 13/13 exact
| View | tok/s |
|---|---|
| control | 55.603 |
| draft_attention | 55.805 |
| control | 55.486 |
| draft_attention | 55.828 |
| control | 55.460 |

Candidate mean 55.817 vs control mean 55.516 (**+0.54%**); each candidate exceeds every control. Drift 0.26%, wall 539 s for 5 views (about 25 min as v4 screens). This is the first lever bracket on the native in-process switch path (packet 98c). The route A/B/A smoke passed earlier at 05:45 (0.32% drift, 339 s for 3 views).
