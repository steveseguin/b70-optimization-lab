# Packet58n: one-card loss explained to the receipt limit; tile16 screen prepared

October 18, CPU-only, main. `git pull --rebase` refused the unrelated dirty
orchestration files; `git fetch origin` confirmed HEAD and origin/main both
at `a7a1ce7f01a41da7f6d45b44e02b0f6993aa02a5` before work. Those files and all
existing packets, screen wrappers and ops files were left untouched.

The losing bundle spends **8.41 ms/token preparing host lookup inputs versus
0.58 ms** for production. Major faults rise from **0.13 to 12.70/token**;
preparation and major faults correlate at 0.985 within the bundle. Its cache
counts, miss bytes and residency match production at every one of 2,386
positions. Cache work and host waits get slightly faster. Sparse file-backed
embedding/PLE lookup reads are the leading explanation for the added host
span; the receipts cannot prove why the page state changed or assign the
regression to one kernel. There is no adjusted speed claim.

The quoted **24.969 / 22.181 tok/s** are all-prompt medians. The registered
class-balanced rates are **24.888 / 21.927**. The old third arm was cancelled;
neither statistic turns this into a complete matched speed verdict.

Tile16 does not change expert bytes or admission. Both retained fresh K1 runs
cut all-host down time from about 0.90 to 0.42 ms; half-host cases also improve.
The CPU decision is therefore **production / down-tile16 only / production**.
Route-fast removes 144 launches without changing the miss path; recurrence
keeps device-only operands and unchanged arithmetic. Both have plausible
positive mechanisms, but neither has isolated one-card timing. Device-only
tiling is deferred: it needs tagged mixed-residency dispatch and conversion
work, and drops the strongest retained host-read benefit.

[Full analysis](../experiments/own-xpu-runtime/stage2/packet58n-onecard-loo/ANALYSIS.md)
includes token/phase summaries, cache/layer inference, unavailable fields,
each source mechanism and byte-exact archived receipt inputs.

The [new proposed queue](../experiments/own-xpu-runtime/ops/lane-queue/proposed-p58n-screen-A.txt)
needs a **33–39 minute whole-host gap** on card 0/lane A. It copies 58k's
one-load-per-arm protocol: two fresh K1 fixtures per arm, all twelve prompts
at 128 tokens, every token checked against packet49, full BF16 KV, unchanged
118.31 GB host timing admission and 8 GiB reserve. The boundary is the newest
validated kernel line minus exactly two seconds. Output is the fresh
`packet58n-onecard-loo/evidence/card0-loo-a/`; no live queue was touched.

Validation: **82 Python checks**, analysis joins and hash checks, the source
and binary seal, and **three temporary queue plans** pass. The copied native
build is **39.53 MB**, byte-identical to 58j; nothing was compiled or executed
on a device. Original parent byte/startup gates are reused with their identity,
not called new runs. All work used nice19/helper cores and Python `-B`, with
CPU analysis/test/plan address-space limits of 8 GB. No GPU, service, sudo,
power/memory/swap/page-cache change, reboot or kill occurred. No record was
submitted. [Handoff and restoration](../experiments/own-xpu-runtime/stage2/packet58n-onecard-loo/README.md),
[closeout](../experiments/own-xpu-runtime/stage2/packet58n-onecard-loo/CPU-PREPARATION-CLOSEOUT.md).
