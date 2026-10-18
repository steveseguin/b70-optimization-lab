# Packet 100 down-projection microbenchmark on REAL routes (2026-10-18 05:22 UTC, lane B)

Packet 100b captured real routed-expert IDs (`packet100b-capture-B`, 05:18–05:20, diagnostic, outputs unchanged). Packet 100's microbenchmark then ran the down kernel at full shapes on those routes (`stage2/packet100b-route-capture/evidence/micro-B/qualification.json`).

| Candidate | Time ratio vs production | Qualified (≤ 0.85) |
|---|---|---|
| down-interleave (expert-interleaved traversal) | 1.000 | no |
| **down-tile16** (lossless 16-row down-weight transpose at load) | **0.695** | **yes** |

Packet 86 bounds down's cache/load cost at about 0.36 ms per rank-1 half (`exp-onecached`). Production down takes 1.21 ms per half. In-engine transfer of micro gains has been about 47% (packet 93). Queued: `packet100-down-tile16-B-grid` (lane B) and `packet100-down-tile16-A-confirm` (lane A, the record lane).
