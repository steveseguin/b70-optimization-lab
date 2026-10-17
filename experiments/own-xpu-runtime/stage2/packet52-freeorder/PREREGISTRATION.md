# Packet52: free-order speed ceiling, preregistered before any device run

This packet asks whether a single new arithmetic identity is worth its CPU
oracle cost. It is a synthetic operator speed-ceiling probe, not engine
integration, a model-quality decision or a published speed claim. No GPU runs
are authorized during preparation. The coordinator owns every device window.

## Binding decision

**Arithmetic v3 proceeds only if the same chosen deterministic variants,
together, save at least 120 microseconds per ordinary M=1 GDN layer in BOTH
fresh timing owners.** An unmeasured or failed gate is pending, never negative
performance evidence and never permission to start an oracle job.

Seven disjoint class groups enter exactly once: expsgate (paired gate/up),
gdn.qkv, expsdown, attention output/combine, hc.low_gate (both attention and
FFN sides), small.ffn.q6 (the production tuple), and gdn.z. Keep all other
work unchanged. For each class and variant, compute the median paired
control-minus-candidate event-time sum over the 200 measured iterations,
separately for each owner. Select one variant per class by greatest minimum
saving across the two owners, breaking ties by variant name. Include the
control as a zero-saving alternative. This produces one common selection,
never different winners for different owners. Sum its seven class savings
separately in each owner; both sums must be >=120 us. The statistic is an
operator-budget sum, not a measurement of an integrated layer or model.

Report every class/variant M=1 and M=2 result, including regressions. M=2 means
two independent rows executed serially as the production engine does; sum
both rows before calculating medians. M=2 cannot substitute for the M=1 bar.
Do not multiply the result by 48 or turn it into an emitted-token estimate.

## Control and shape identity

The control is packet49c's accepted dispatch: packet48b compact expert gate/up
and down, packet51 HC low/gate and attention winners, packet45 remaining dense
and small-FFN kernels. The quoted 96.7/37.2 us QKV/Z values were packet48b
candidate measurements, not adopted production controls. Controls are measured
again alongside candidates. The production route selects TEN experts, not
eight; the exact census and fixture use ten and distinct changing routes.

Use ordinary GDN shapes at layer4 from the retained census and full packed
byte layouts. Synthetic finite scales and varied activations are allowed;
no weights are downloaded or changed. Preserve all downstream nonlinear,
BF16-store and combine boundaries within each measured class. Candidate
partial sums and deterministic second-stage reductions count in GPU timing.

## Arithmetic and exactness

Each candidate has a named fixed order, an independently traversed CPU mirror,
explicit FP32 multiply/add boundaries (no implicit FMA), and a fixed adjacent
reduction tree. No atomics, races, floating-point unordered reductions or
runtime order selection are allowed. The implementation manifest freezes the
small named family before the source/build seal and before any device run.

CPU checks run serially at nice19 on cores4-15,20-31; no model oracle job is
started. E1/E2 are distinct fresh device processes. Every admitted variant,
class, M=1 and both M=2 rows must compare all final outputs and observable
intermediates with its OWN CPU mirror, byte for byte. Fresh output identities
must agree. Record numeric distance to the unchanged order for information
only; a changed answer is not a failed own-order gate. CPU success alone does
not establish GPU exactness or full-model quality. Nonfinite cases require an
explicit admissibility policy rather than silently relaxing equality.

T1/T2 require both E receipts, their native hashes, the same sealed source and
binary, physical card0 / PCI0000:23:00.0, environment, boot and fault-review
boundary. Both run once in separate coordinator-owned processes, with ten
warmups and 200 measured paired iterations. Alternate order to limit bias;
retain all compute event endpoints. Initialization, fixture generation,
reference computation, transfers and output readback stay outside GPU timing.
No profiler, prompt reuse, learned draft or runtime cache is part of this test.

## Bounded windows and safety

Each T owner has a 1,140-second cooperative watchdog, leaving roughly a minute
under the 20-minute planning bound for journal postflight and drain. Expected
runtime is estimated from the frozen case count and measured CPU preparation;
see WINDOW.md. If a window overruns, retain incomplete evidence and stop;
do not retry or reduce the case matrix after observing performance.

Use script-file systemd user windows, closed environment, explicit
zombie-tolerant memory sensor, passive foreign-client admission, and ongoing
kernel-fault supervision inherited from packet51. SIGTERM requests a drain;
no hard kill or automatic restart. A fault is retained for the coordinator's
standing recovery process. No preparation step changes services or host
settings. Keep the new packet's build below 1 GB and protect packet49c's
reserve and both named running units.

## Outcome handling

If both owners meet the bar and E passes, ARITHMETIC-V3.md is completed with
chosen class/order identities, exact CPU mirror changes and one combined
oracle cost estimate (about five hours with two workers, to be rechecked).
The oracle and packet53 integration remain separate work; this packet starts
neither. Otherwise record the measured per-class ceilings and a negative
closeout. Until device windows exist, the outcome remains PENDING.
