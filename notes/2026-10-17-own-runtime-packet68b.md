# Packet 68b — batched target rows, October 17

The shared-weight two-row probe is built and sealed for the coordinator.
No GPU, model run, service, sudo or host setting change ran here. All frozen
packets, screen sources and ops files were left alone.

Dense projections, target HC and the IQ2 gate/up + IQ4 down expert union now
have independent row accumulators fed by shared decoded weights. GDN, conv,
QSA attention cores and remaining operations retain serial row arithmetic.
GNU and Intel host fixtures each pass 1,308 byte checks and agree across
compilers. They cover different row inputs/routes, repeated and partial routes,
invalid routes, signed zero, nonfinite activations, inactive/error controls and
context bounds. Native compilation and lane-B plan admission pass.

The probe uses the current real inputs at three generated positions on each
half. It compares two private row outputs and persistent state against a
private production M=1 replay, restores the original bindings, then resumes
normal generation. The screen still requires all thirteen packet49 streams
to match. H1/H2 order alternates; class events, wall/device spans, copy cost,
request identity and coverage are logged. This is a duplicate independent-row
screen, not a causal verifier or a new speed claim.

The frozen wrapper admits only 23/25 for unknown packets; its rank1 budget has
too little room for private images. A small packet-local supervisor/worker
bridge admits the audited 24/24 choice and preserves the frozen wrapper's
fault, lane, hold, drain, unit and oracle checks. The memory plan adds a
512 MiB per-rank ceiling, checked before cloning and included in READY census.
The watchdog is 3,600 seconds for an estimated 5–8 minute run.

The analysis helper requires completed exact device evidence, then computes
per-half/class ratios and a two-token pipelined projection at the +8% bar.
Both rejection cases, a second draft and restore cost are explicit. Missing
restore evidence yields only a zero-cost sensitivity. A depth-one redo does
not earn an extra token merely because it processed a second row.

**Decision pending the coordinator's measurements.** Neither the CPU gates
nor a compiled binary measures H(2)/H(1). The next action is the sealed lane-B
window, then the analysis command in the [packet README](../experiments/own-xpu-runtime/stage2/packet68b-batched-rows/README.md).
