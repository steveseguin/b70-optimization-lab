# Packet132: a second draft choice does not clear the cost gate

The CPU study is closed. The main cost model chooses to leave the second
candidate disabled: 0.00% projected gain. Every threshold that enables it
projects a slowdown. Even counting only extra expert work gives +2.25%, below
the required +3%; that threshold gives +1.77% on the held-out text.

We captured 24 target tokens from each of five fixed excerpts of packet114's
independent text. Of 56 first-choice misses, the second choice matches 13.
Allowing both choices everywhere would raise acceptance from 53.33% to 64.17%,
but adds too much work. A confidence margin below 1.125 selects 38 of 120
cycles and rescues nine misses. Its projected change under the main costs is
−1.08%. The best +3% cost budget is only 1.952223 ms per selected cycle,
against the main estimate of 4.153946 ms.

These are small-sample CPU observations and cost projections, not measured
device speeds. The CPU draft is not certified numerically identical to the
device draft. The timing source failed its instrumentation overhead gate,
and actual two-candidate timing and expert sharing remain unmeasured.
The report keeps those limits, the 21%-miss sensitivity, and the separate
training and held-out results explicit. Benchmark prompts and outputs did not
supply calibration or evaluation rows; the report discloses incidental viewing
of old encoded input metadata during source inspection.

Capture finished in 48 minutes 11 seconds, using at most 1.16 GB of sampled
combined memory. All 13 child stages exited normally. Eight analysis tests,
source checks, exact result recomputation and evidence retention checks pass.
The whole study completed within the 90-minute budget. No GPU, service, sudo,
settings, live queue or production runtime changed. No candidate was implemented.
The capture process has exited; original evidence remains intact.

The next condition for reopening this arm is a concrete way to bring the
complete extra half below its cost budget, or a better predictor tested on new
independent text. Retuning these rows is closed. Packet131's existing spare
bank is not assumed available for a sibling.

- [Analysis and cost breakdown](../experiments/own-xpu-runtime/stage2/packet132-two-candidate/ANALYSIS.md)
- [Full threshold table](../experiments/own-xpu-runtime/stage2/packet132-two-candidate/thresholds.csv)
- [Machine-readable decision](../experiments/own-xpu-runtime/stage2/packet132-two-candidate/result.json)
- [Closeout](../experiments/own-xpu-runtime/stage2/packet132-two-candidate/CLOSEOUT.md)
- [DO-NOT-REPEAT entry](../experiments/own-xpu-runtime/stage2/packet132-two-candidate/DO-NOT-REPEAT.md)
- [Evidence identities and restoration](../experiments/own-xpu-runtime/stage2/packet132-two-candidate/evidence/capture/retention-manifest.json)
