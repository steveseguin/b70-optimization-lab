# Packet156: the proposed draft window is too short

The full packet154 test confirms that rank 0 waits for the draft. But the
proposed place to move part of that draft has almost no waiting time to use.
We replayed the smoke and all five views, keeping both ranks' original logs.
Even giving the idea more time than it could really use would allow only
about 0.29–0.32% improvement in the three controls. The goal was at least 2%.

We closed this arm before writing a runtime or launching another test, as the
brief required for a small bound. The analysis and 14 parser checks pass;
`ready_for_device` is false. Both-lane proposals and native build checks were
not created or claimed. No GPU, service, existing packet or live queue changed.
The 58.798 tok/s record stays unchanged.

We also checked the next prepared ideas. The existing snapshot test has
finished at about +0.35%, below its gate. The other prepared ideas still lack
enough measured removable work. An earlier place to schedule draft work needs
different timing evidence; this result does not rule that out.

[Full closeout, exact bounds and replay commands](../experiments/own-xpu-runtime/stage2/packet156-draft-slack/ANALYSIS-CLOSEOUT.md).
