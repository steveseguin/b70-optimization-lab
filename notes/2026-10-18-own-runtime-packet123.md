# Packet 123 — partial-layer placement held at the slack gate

Bundle 7's twelve saved lane-B requests give **932 hit / 256 miss** first-99
intervals. Rank 0's recorded command time is **12.853664 / 25.254390 ms**
(hit / miss), with **2.107083 / 0.549188 ms** outside those commands;
rank 1 records **14.940611 / 14.989112 ms**, with **0.020136 / 10.814465 ms**
outside. Packet108's formula returns an apparent **0.482640 / 0.535270 ms**
rank-0 tail, but packet105b's suffix head runs outside the command trace and
rank 1 waits for it. The logged copies alone take at least **0.043010 ms**
per head service; suffix computation and its wait have no timestamps.
Usable hit slack is therefore **unknown**, with only a loose mean upper bound
of **0.439630 ms**. This proves neither the required ≥0.3 ms admission nor
a <0.3 ms rejection. The partial-layer preparation is blocked at that gate;
no placement implementation, build, smoke, seals or queue proposals were made.
The next prerequisite is separately timed rank-0 head service and rank-1
head readiness in an authorized device window. No GPU, service, live queue,
frozen source, host setting or other worker's files changed.

[Accounting, reproducibility and limitations](../experiments/own-xpu-runtime/stage2/packet123-partial-placement/README.md),
[machine-readable results](../experiments/own-xpu-runtime/stage2/packet123-partial-placement/slack.json),
[closeout](../experiments/own-xpu-runtime/stage2/packet123-partial-placement/SLACK-CLOSEOUT.md).

The requested `git pull --rebase` refused unrelated dirty orchestration files.
`git fetch origin` confirmed `main`, with HEAD and origin/main both
`c06bd6a0f8b965231fef2b5706998ac0c9c99407`. Placement history checked:
packets63, 79, 108, 118 and 120. The first raw extraction appeared to admit
the move; source inspection and an independent read-only review caught the
untraced head service before any implementation. The raw formula is retained
and explicitly labeled as contaminated, not silently replaced with a guess.
All Python analysis runs nice19, CPUs8–15/24–31, `-B`, closed stdin, with
the 8 GiB cap only in CPU entry processes. No compiler was needed. Root
remained above 35 GB free; the retained analysis is under 2 MB and has no build.
