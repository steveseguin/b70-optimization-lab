# Packet135 — critical-path synthesis, October 18

The 58.22 record is explained by 14.905 ms hits and 25.702 ms misses. The first 99
intervals contain 932 hits and 256 misses; the pooled mean is 17.231 ms/token.
Recomputing the actual class-balanced metric gives exactly 58.2238342935355
tok/s. The difference is aggregation, not unexplained runtime time.

The important correction is the host token path. In the record it takes about
0.102 ms and reports zero major faults. Packet134's 1.5–1.9 ms preparation
belongs to the slower instrumented run and cannot be used as record headroom.
Likewise, the gap between the ranks includes head-suffix work; it is not free
space for more layers. Draft kernels sit inside the draft command, and miss
correction already overlaps drafting.

The [analysis](../experiments/own-xpu-runtime/stage2/packet135-critical-path/ANALYSIS.md)
recommends finishing the pending recurrent snapshot test first. Removing
0.20–0.30 ms of actual serial copying projects +1.18–1.78% if suffix service
advances with it. The second proposal combines an exact, complete immutable
draft-embedding projection table with faster target token preparation. Its
central projection is +0.62%; it falls below 0.5% when too much of the rank0
saving is hidden. Both include concrete one-load switch/reset designs and
require exact smoke before a matched bracket. Neither is a measured win or a
newly qualified runtime; no GPU proposal or implementation was made.

All 157 repository negative indexes and the closed ledger are pinned. Today's
losing placement/head/draft/kernel arms stay closed. The practical planning
band for these small remaining mechanisms is roughly 59–60 tok/s, not a claim
that the pipeline or lane is finished. The analysis retains uncertainty,
per-segment floors, unknowns, all relevant measured identities, the 20% ordinary
kernel-transfer discount and the full serial/draft transfer assumptions.

[Reproducible calculations](../experiments/own-xpu-runtime/stage2/packet135-critical-path/model.json)
and original-byte inputs accompany the report. The check reconstructs all 1,188
intervals and the headline exactly; it also rechecks the failed 128b overhead
gate and both completed 122 draft micros. The 1.52 MB compressed input snapshot
is intentionally retained because the new record host-timer evidence and
completed diagnostic inputs were local/ignored. Restoration instructions and
the reason for the size are in the analysis. No originals were removed.

CPU only on steve-b70s: nice 19, CPUs 8–15/24–31, Python -B, stdin /dev/null,
4 GiB process address-space cap. First full reconstruction used 163,472 KiB
peak RSS; no build, weight read, GPU, service, sudo, settings or queue change.
The initial pull refused unrelated dirty files; fetch confirmed
`fa38e9f973172cfa915f25e2cc6a4b7b5d513967` equaled origin/main. Other workers
advanced main during the task. Existing dirty 128b and orchestration files
remain untouched. CURRENT.md also became dirty concurrently and is not part
of this analysis-only commit. Commits use explicit task paths and are pushed
immediately, with the requested coauthor trailer.
