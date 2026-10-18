# Packet140 — next target-body lever, CPU decision

The [ranked table](../experiments/own-xpu-runtime/stage2/packet140-body-lever/ANALYSIS.md)
closes this packet without a device candidate. No new exact mechanism supports
the required 3% gain. The 58.223834 two-card record stays unchanged.

The retained record needs about 0.413 ms saved per target half, including the
extra half on misses. At 20% transfer that requires 2.064 ms of raw operator
savings. The largest single-class scenario gives about 0.49%. Applying the
same proposed scale sharing across every possibly eligible class gives 1.31%.
It could cross 3% only with at least 45.22% transfer of those assumed savings;
the earlier load-issue experiments do not support that assumption. An 80%
sensitivity is retained openly at 5.43%, not admitted as a forecast.
These are calculations, not measured speeds. Packet128b failed its timing-overhead gate; its body
times are diagnostic proxies for bundle8's unchanged kernels, not ordinary
bundle8 measurements. Packet110's old down/fusion gaps cannot be reused.

The audit retains all 164 repository negative indexes, their hashes, search
matches and the closed ledger. It distinguishes three source-level ideas:
sharing identical scale bits between lanes, a same-size IQ2 integer metadata
layout, and producer-side RMS partials. None earns implementation under this
brief's gate. Closed tile16, lookup, geometry, fusion and recurrence attempts
stay closed; the ongoing packet136/137/139 work is untouched.

Work began at 17:08 UTC on `steve-b70s`. `git pull --rebase` refused unrelated
dirty files; `git fetch origin` confirmed HEAD and origin/main both at
`1533175ff131db1c811c98530e1b7e54b7bb9a61`. Root had about 33 GB free,
above the brief's 25 GB stop threshold. The CPU analysis runs with nice19,
cores 8–15/24–31, Python `-B`, no stdin and a 4 GB address-space cap only
inside its main process; initial peak RSS was 118,220 KiB. No build is needed.

Because the selection gate fails, the conditional implementation, byte gates,
entry probes, admission, device proposals and readiness marker are not created.
No GPU, service, sudo, host setting, live queue or other job was touched.
The table and its reproducible evidence are committed first; the final
closeout and current-state pointer follow after review.
