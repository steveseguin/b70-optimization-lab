# Packet58ag: one-card target refinements

Started 2026-10-18 at 23:06 UTC; three-hour limit. Pull refused pre-existing
dirty orchestration files. Fetch confirmed HEAD and origin/main both at
`34423d4cfdf3f81f5277c96f1dbbee54491cf28d`. Root had 31.1 GB free.

The private symlink-preserving packet58ab copy adds HC-wide, exact half-scale
caching, and packet109's small target fusions as runtime choices. HC fusion
stays on. The half-scale cache is a 256 KiB table covering every FP16 bit
pattern, preserving the existing packed weights and one-card cache layout.
The literal packet90 larger-row layout is not used. Packet109's fused router
includes exact route-fast; no standalone packet58r rerun is proposed.

The [audit](../experiments/own-xpu-runtime/stage2/packet58ag-onecard-ports/AUDIT.md)
records the other two-card selections and their exclusions. In particular,
rank1 ordered retirement needs a separate proof for asynchronous one-card
ownership; head splitting requires two devices. CPU tests and compilation
use nice19, cores 8–15/24–31, closed stdin and at most 4 GiB. Compilation uses
the shared turn gate. No GPU, service, model payload or live queue is touched.

Source milestone: private closure and the three ports are implemented;
GNU/Intel compilation and byte checks are in progress. Device quality and
speed are pending. READY will be the final content write.
