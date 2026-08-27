# Qwen3.8 27B Q4_K_M + MTP2 — one-B70 candidate package

**Strict headline: `42.636988 tok/s`.** Two fresh servers measured
`42.600910` and `42.673065` on the fixed twelve-prompt/six-class 512-cap
suite. Both attempts passed cache-zero and objective canary gates and matched
all 12 complete token arrays against each other and the same-build target-only
control. The control measured `27.375682 tok/s`, so MTP2 added **55.75%**.

This is a separate deployment from the no-MTP Q4 package because it requires
a second 1.37 GB draft download. Use the complete
[reproduction guide](../../repro/qwen38-27b-q4km-mtp2-tp1-b70/README.md);
it links every required patch and pins the target, draft, server, and SYCL
backend identities.

MTP2 is deliberate. MTP1 was slower (`38.320`), MTP3 was slightly slower
(`42.123`), and MTP5 changed all twelve target outputs and is rejected.

A separate cache-zero exact-depth sweep measured target-oracle-exact MTP2
decode at 4K/8K/16K/24K/32K. The exact 32K point is `37.583325 tok/s` with
`39.439 s` TTFT. This is Grade D repeated-token shape evidence, not natural
prose. The 2K fixture reproducibly diverged at generated token 23 and remains
quarantined, so MTP2 is not claimed universally target-exact. The target-only
or MTP2 concurrency curves do not transfer; exact MTP2 concurrency remains
open until measured directly.
