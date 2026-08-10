# Canonical Q8 Phase-1 idle-unload negative result

Date: 2026-08-09 local / 2026-08-10 UTC

## Classification

The sleep-idle teardown-evidence hypothesis is rejected. The fresh four-card
wave completed all four sequential c1 oracle captures, but selector-on lanes
did not produce or retain the required canonical process summary during the
server's intentional idle-sleep lifecycle. The wave failed closed and is
diagnostic only. Nothing in this packet is a Phase-2 handoff or a performance
result.

Failed packet:

`/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/canonical-q8-c1-oracle-four-gpu-20260810T004245.863756594Z`

- exhaustive `wave-artifacts.sha256` SHA-256:
  `46f2509d92690954e3029e2da9426d90457224877696134c817023c0045928e5`;
- detached failure-marker SHA-256:
  `ec712243d3d711432703144359ee2bba20c02c948435d7f3882549c51286f17a`;
- classification: `FAIL`, `diagnostic-only-failure`,
  `performance_promotable=false`;
- all 310 manifest entries verified.

## Diagnostic observations

All four fresh c65536/np2/non-unified-F16-KV servers completed the fixed A+B
sequential capture. Every oracle passed its intrinsic gate, retained 512 exact
forced tokens per case, and recorded the expected sequential diagnostic
occupancy of 1,024 predicted tokens across 1,032 decode calls. Those counters
are retained only to classify this failed attempt; they are not a speed or c2
concurrency claim.

The exact A row was identical on all four cards:

- token-array SHA-256:
  `c9754bee39df823b7450c1793a0824f6f3e115f6831cf4281dc2a5a323c6cf91`;
- content SHA-256:
  `0d9d47550a141926d07655a6bfc32600e09604c5fc004e4daa1e7001078800d1`.

The exact B row was also identical on all four cards:

- token-array SHA-256:
  `415b37ddb9199a6ec992660ff0aab92842af1c21f50ff454ae86029ba59457a7`;
- content SHA-256:
  `aaad8a7d750cf67a188520e3c96ffb30d77a1f58f6df52b45022e2863dc5fee5`.

For completeness, the two-card means from this failed simultaneous wave were:

| Case | Selector | Prompt processing tok/s | TTFT s | Full-512 tok/s |
| --- | ---: | ---: | ---: | ---: |
| A | off | 154.165 | 28.350 | 15.0569 |
| A | on | 154.787 | 28.236 | 15.0509 |
| B | off | 158.729 | 27.207 | 15.0594 |
| B | on | 159.200 | 27.127 | 15.0515 |

These card-confounded diagnostic means suggest roughly `+0.3%` to `+0.4%`
prompt-processing movement and `-0.04%` to `-0.05%` decode movement. They do
not establish a speed win: the wave was neither isolated nor same-card
bracketed, its evidence gate failed, and no performance promotion is permitted.

Selector-off lanes on GPUs 0 and 1 sealed successfully. Selector-on lanes on
GPUs 2 and 3 each retained the exact flat first-hit and no recurrent or
violation marker, then reached one queue sleep plus one server sleep and timed
out after 180 seconds with no canonical summary. The packet contains no forced
kill, cleanup survivor, relevant residual process or listener, passive device
fault, or active post-failure XPU probe.

## Conclusion and replacement contract

The canonical summary is emitted from the SYCL backend-free source path. This
idle-sleep lifecycle produced or retained no summary; the packet cannot
distinguish failure to reach backend-free from failure to retain its late log.
There is therefore no evidence that simply waiting longer on the unmodified
mechanism will succeed. The sleep/keeper path is removed from Phase 1 and is
not carried into the Phase-2 identity.

The replacement requires a wholly fresh four-lane cohort:

- selector off: exact no-sleep server identity and zero canonical first-hit,
  summary, or violation markers;
- selector on: exact no-sleep identity, exactly one well-formed flat first-hit
  retained before release, no recurrent first-hit, and no violation marker;
- a selector-on summary is optional; if present it must be unique,
  well-formed, internally consistent, flat-positive, recurrent-zero, and
  violation-zero, but its totals are neither compared nor claimed;
- the full A+B 512-token correctness, official/adapter comparisons, PID and
  runtime binding, graceful teardown, global passive health, and exhaustive
  sealing gates remain unchanged.

The failed packet and its otherwise exact oracles remain negative evidence
only. They must not be salvaged, copied, or promoted into the fresh Phase-1
handoff.
