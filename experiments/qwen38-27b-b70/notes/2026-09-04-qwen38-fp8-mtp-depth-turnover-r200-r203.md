# R200-R203: MTP depth turnover on the R187 line (single user, strict suite)

Date: 2026-09-04 01:50-03:20 EDT, boot 88f0984f. R156 image, `splitting_ops=[]`, strict pairs vs the R187
same-configuration MTP0 oracle. Results `data/2026-09-04-qwen38-fp8-r200-whole-graph-depth5-strict-result.json`,
`data/2026-09-04-qwen38-fp8-r202-r203-depth6-depth7-result.json`.

| depth | a / b tok/s | center | gain vs previous | identity |
|---|---|---|---|---|
| 1 | 55.006 / 54.865 | 54.935 | | 12/12 (R188) |
| 2 | 70.146 / 70.138 | 70.142 | +27.7% | 12/12 (R187) |
| 3 | 79.163 / 79.203 | 79.183 | +12.9% | 12/12 (R191) |
| 4 | 82.447 / 82.345 | 82.396 | +4.1% | 12/12 (R197) |
| 5 | 86.266 / 86.097 | 86.182 | +4.6% | 12/12 (R200) |
| 6 | 87.239 / 87.048 | 87.144 | +1.1% | 12/12 (R202) |
| 7 | 85.937 / (fault) | 85.937 | -1.4% | a 12/12 (R203) |

Acceptance per position: d4 0.893/0.828/0.562/0.521 (mean 3.80); d5 0.857/0.741/0.536/0.415/0.330 (mean 3.88).

Reading: the single-user rate peaks at depth 6 and turns down at 7. By the preregistered 2% bar, depth 5 is the
deepest candidate (depth 6's gain is within run-to-run noise); depth 4 is published (identity c1-c16 in two
ladders). Every depth is lossless on the strict suite by construction and by measurement. Depth 5's probe and two
ladders (R204) were blocked: at 02:35:46 device 0000:03:00.0 logged `Fault response: Unsuccessful -EINVAL` and a
coredump during the depth-7 candidate-b weight staging (the recurring copy-engine fault during staging); the
runner's preflight then refused every further launch on this boot. No reboot overnight (user instruction). Next
after a reboot: R204 (depth-5 ladders x2), R199c (short profiler window), then a depth-6 pair repeat if the user
wants the last 1%.

## R205 (2026-09-04 10:12-10:19, clean boot 4634e845): depth-6 pair repeat

87.145 / 87.095 tok/s, 12/12 vs sibling and vs the R187 MTP0 oracle. Four depth-6 servers now span 87.05-87.24
and four depth-5 servers 86.10-86.27: the +1.1% of depth 6 over depth 5 is reproducible (server-to-server noise
about 0.2%) but below the preregistered 2% bar. Depth 5 keeps the "deepest candidate" label by that rule; the
user may prefer depth 6 for the last 1% at the cost of more rejected work at c32+ (depth 4 already loses to
depth 2 above c16).
