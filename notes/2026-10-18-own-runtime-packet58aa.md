# Packet58aa: one-card MTP re-check

October 18, 2026, steve-b70s. CPU-only review of saved evidence, under the
owner's 60-minute brief. No GPU, service, sudo, model read or setting change.

**Decision: no build.** The measured host bound removes 58h's old RAM blocker.
A conservative draft extension needs 103.314 GB available, below the saved
119.233 GB floor. But the current device budget is already full: keeping its
driver allowance and 1.5 GB reserve leaves only 18.216 GB of target cache with
a resident draft, down from 21.553 GB.

The independent saved text routes average 16.52–16.78 experts in a two-position
union, versus 10 for one position. Cache replay and the retained timing proxies
project 25.03–29.16 tok/s with resident drafting. Even a favorable shared-cache
case reaches only 30.62 before charging draft misses and cache pollution.
The requested +5% threshold is 30.723. These are projections, not new speeds.

The [analysis](../experiments/own-xpu-runtime/stage2/packet58aa-onecard-mtp-recheck/ANALYSIS.md)
records exact memory arithmetic, per-layer route growth, extra zero-copy bytes,
draft/verification/state assumptions and all source hashes. The
[new negative entry](../experiments/own-xpu-runtime/stage2/packet58aa-onecard-mtp-recheck/DO-NOT-REPEAT.md)
updates the reason to leave this composition closed without changing frozen
58h. The [closeout](../experiments/own-xpu-runtime/stage2/packet58aa-onecard-mtp-recheck/CLOSEOUT.md)
requires a supported complete causal cycle under 58.164893 ms before reopening.

All CPU analysis uses `nice -n 19`, cores `8-15,24-31`, `python3 -B`, stdin
`/dev/null`, and a 4 GiB address-space cap. The first replay peaked at
127,508 KiB RSS; the final replay peaked at 129,508 KiB. Source hashes, route counts, reserve arithmetic and all 64
scenario outcomes are checked by `analyze.py --check`. No runtime or test
fixture pretending to be device evidence was produced.

`git pull --rebase` refused the pre-existing dirty orchestration files.
After `git fetch`, upstream contained two unrelated commits; their diff had
no unexpected deletions. A clean fast-forward synchronized main at
`aa39bad5e306d8b41dfeffad64dcabb0aec109b0` without touching those local edits.
Only this new packet, this note and a short CURRENT.md entry belong to the
task commit, using `git commit --only --` and an immediate push.
