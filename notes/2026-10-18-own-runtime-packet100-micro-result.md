# Packet 100 down-projection microbenchmark on REAL routes (2026-10-18 05:22 UTC, lane B)

Packet 100b captured real routed-expert IDs (`packet100b-capture-B`, 05:18–05:20, diagnostic, outputs unchanged). Packet 100's microbenchmark then ran the down kernel at full shapes on those routes (`stage2/packet100b-route-capture/evidence/micro-B/qualification.json`).

| Candidate | Time ratio vs production | Qualified (≤ 0.85) |
|---|---|---|
| down-interleave (expert-interleaved traversal) | 1.000 | no |
| **down-tile16** (lossless 16-row down-weight transpose at load) | **0.695** | **yes** |

Packet 86 bounds down's cache/load cost at about 0.36 ms per rank-1 half (`exp-onecached`). Production down takes 1.21 ms per half. In-engine transfer of micro gains has been about 47% (packet 93). Queued: `packet100-down-tile16-B-grid` (lane B) and `packet100-down-tile16-A-confirm` (lane A, the record lane).

## Lane-B grid (2026-10-18 05:24–05:38 UTC), all 13/13 exact
| View | tok/s | hit ms | miss ms |
|---|---|---|---|
| production | 55.578 | 15.652 | 26.908 |
| **down-tile16** | **56.619** | **15.350** | **26.427** |
| production | 55.684 | 15.619 | 26.870 |

**+1.68% over the stronger control.** Hit −0.27 ms, miss −0.44 ms. The largest single exact lever measured tonight; the microbenchmark (0.695× kernel time) carried well into the engine. The lane-A confirmation (record lane) started at 05:38. If it holds, down-tile16 enters bundle 5 (packet 103) with packet 97's selection and packet 101's draft attention.

## Lane-A confirmation (record lane), 05:38–05:52 UTC, all 13/13 exact
| View | tok/s | hit ms | miss ms |
|---|---|---|---|
| production | 55.481 | 15.704 | 26.872 |
| **down-tile16** | **56.643** | **15.389** | **26.379** |
| production | 55.473 | 15.707 | 26.922 |

**+2.09% over the stronger control on lane A**; +1.68% on lane B. down-tile16 is confirmed on both lanes, the largest exact lever of the night. It enters bundle 5 (packet 103) with packet 97's selection and packet 101's draft attention.
