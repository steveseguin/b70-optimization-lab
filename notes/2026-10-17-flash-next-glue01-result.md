# Flash-Next FP8 glue01 row-copy screen: result (2026-10-17) — CLOSED, exact but neutral

This was a sealed control/candidate pair (packet `a367-glue01`, seal `7ef8a84b`, after the arm-name fix `eab78e645`). Both arms ran on boot `2cba7160` through the resolved-fault admission:

- the 2 recorded fault lines from 01:09 were accepted only as the exact set;
- no new fault lines appeared through either run;
- each arm had a fresh server, a fresh health pass, the record server profile (nice 0, CPUs 0-31, OMP=1), and one SIGINT after its suite and battery, followed by a full 305 s watch.

| | Control (record identity) | Candidate (+ `Q38_M2_GLUE_ROW_COPY=1`, patch01) |
|---|---|---|
| Launched (UTC) | 01:36:56 | 02:11:29 |
| Realistic suite outputs vs record | **12/12 identical** | **12/12 identical** |
| Battery: quality 6/7 (known code exception), 16/16 repeats, needle, exact 2K/4K × 2 | passed | passed |
| Candidate four-rank byte gate (warmup) | — | passed |
| **Class-balanced 99-interval median** | **44.526 tok/s** | **44.702 tok/s** (+0.4%) |
| All-prompt median | 44.007 | 45.032 (+2.3%) |
| Acceptance (timed suite) | — | 0.757 |
| Clean exit / owners gone / watch | yes / yes / yes | yes / yes / yes |

**Verdict.** The candidate is exact but neutral. The +0.4% gain on the record metric is far inside the 3-10% control-to-control drift, so under the preregistered rule ("a flat result inside ~3% short-term drift closes this small lever immediately") the lever is closed and not extended into a grid.

**Why both arms are slower than replay c (47.11 tok/s).** Codex CPU jobs were reading files on the coordinator cores during both timed suites, and the two arms shared that same light background. The pair comparison is valid; absolute speeds are not record evidence.

Evidence:

- `data/2026-10-17-flash-next-a367-glue01-build/comparison.json`;
- `window-a367g-20261017T013301Z-{control,candidate}/run/`;
- the first, voided campaign: `campaign-void-seal2b7f8c76-duplicate-arm-output.json` and `window-a367g-20261017T012428Z-c/`.

**Next for FP8:** the traced M=2 census on a fresh boot (rendezvous design `7a5176c5d`) to find the larger 2-4 ms levers.
