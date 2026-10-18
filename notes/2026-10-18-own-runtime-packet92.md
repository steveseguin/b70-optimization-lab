# Packet92: rank-1 reply before host reporting

## Attribution milestone

The next draft waits for rank1 accept, so sending a half reply before doing the
same bookkeeping is insufficient. The candidate will retain result waits,
ordered retirement, profiling safety checks and resource snapshots, then move
receipt formatting/output after the next asynchronous draft submission. All
remaining fields will be frozen at the half boundary. Errors in deferred work
must refuse the next half. [Ordered source audit](../experiments/own-xpu-runtime/stage2/packet92-rank1-reply-first/ATTRIBUTION.md).

`git pull --rebase` refused unrelated unstaged running-chain work. Fetch showed
HEAD and origin/main equal; no stash, reset or frozen-tree mutation was used.
Host is steve-b70s; root initially had 19 GB free. No compiler was active.
CPU only, low priority, cores 8-15,24-31, 8 GiB process limit and serial compiles.
No GPU, service, sudo or host setting change. Device savings remain unknown.
