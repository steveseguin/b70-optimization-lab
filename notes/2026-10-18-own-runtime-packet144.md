# Packet144 — two-card wrong-guess study, October 18

The ranked table finds no new exact mechanism with a supported gain of at
least 3%. The current 58.798 record needs about 2.338 ms saved on each miss.
Hiding all restoration would save at most 0.691%. Rank1 already runs the
available draft while rank0 repairs the guess. Earlier proof that a guess is
wrong does not identify the corrected token.

[Ranked analysis](../experiments/own-xpu-runtime/stage2/packet144-miss-path/ANALYSIS.md)
comes first. Its calculator reconstructs bundle7 and bundle8 from the original
twelve-request receipt archives and retains the full 176-file negative-index
audit. It keeps instrumented timing separate from ordinary record intervals.
The only larger new direction, sharing corrected rows/experts across cards,
has no measured transfer or admitted memory plan; its favorable scenario does
not pass the gate.

Milestone 1: ranked analysis, reproducible arithmetic and frozen source/audit
snapshot committed as `a00b33d36` and pushed immediately at 20:29 UTC, within
the first 30-minute deadline.

Milestone 2: consistency review, explicit conditional bounds and a concrete
miss-conditioned draft-head completion check. Only 20 of the 256 target labels
could benefit from added head rows; even a free rescue of all 20 is +1.233%
in the recorded model. No prefix was selected or retuned from these labels.
The [closeout](../experiments/own-xpu-runtime/stage2/packet144-miss-path/CLOSEOUT.md)
and local DO-NOT-REPEAT entries retain all decisions. Final calculator checks
and source review pass; peak RSS was about 163 MiB. All 26 local document links
resolve and the seven captured packet136 files remain byte-identical. No
design or device proposal is admitted. The study and closeout were completed
within the 60-minute box.

Host: `steve-b70s`. Work stayed on main. `git pull --rebase` refused existing
unrelated dirty files; `git fetch origin` confirmed HEAD equaled origin/main
at entry (`d4312dbce56bdec01b69c0b6aef98333a4507b40`). Unrelated orchestration
changes, packet128b's dirty budget and all frozen packet trees are preserved.
The budget's observed bytes are retained in this packet rather than edited.

All analysis commands use nice19, cores 8–15/24–31, `python3 -B` where relevant,
stdin `/dev/null` and a 4 GiB cap for the calculator. No GPU, service, sudo,
setting, queue or model/full-shape read was used. A read-only source audit ran
in a subagent under the repository's instruction to delegate read-only work
while existing GPU work is busy. No live-state change was made, so CURRENT.md
is left to the active orchestration owner.
