# Packet53 preparation findings

Device round closed below its 30 µs bar; preserve negative evidence.

| Finding | Outcome | Revisit condition |
| --- | --- | --- |
| Pass a proof's retained lane array to `iq3::tree32(float*)`, then reuse it | First CPU proof failed at check6, V1 adjacent tree; the production helper reduces its input in place | Reduce a private copy; preserve raw lane arrays for all independent comparisons |
| Treat a passing own-mirror comparison as production equivalence | Rejected in parser negative controls; all candidate hashes must crosslink to the actual same-case production capture | Never waive production-byte equality in this packet |
| Treat a future scheduled time as a fault-review boundary | Wrapper refuses before launch | Coordinator must pass an actually reviewed past UTC boundary |
| Repeat packet52's per-short-workgroup SLM table fill | Already slower in packet52; not a candidate here | Persistent64-workgroup fill is a distinct registered hypothesis, with identical-order global control |

[Initial proof refusal](evidence-cpu/initial-proof-refusal/README.md) retains
the rejected test source and original build receipts. The correction changes
test scratch ownership, not kernel arithmetic or the expected result.

The next cross-compiler gate found a second fixture bug: two RNG calls in the
arguments of `ldexp` had no specified evaluation order. Each compiler passed
all8,432,381 internal checks but tested different adversarial tree values.
Draw mantissa and exponent in separate statements; never weaken the cross-
compiler hash gate. Intel also prints the expected one-thread-limit warning
before JSON; the wrapper now accepts only that exact warning/hint prefix and
preserves it in native.log. It does not raise the CPU thread limit.

[CPU preparation closeout](CPU-PREPARATION-CLOSEOUT.md).

## Device closeout (2026-10-17)

| Arm | Outcome in both fresh timing owners | Revisit condition |
| --- | --- | --- |
| Persistent gate/up global, 64 workgroups | About 138 µs slower per layer | A different occupancy/scheduling mechanism with a new preregistration |
| Persistent gate/up SLM | About 215 µs slower | Do not repeat this table staging geometry |
| Persistent virtual2 gate/up SLM | About 218 µs slower | Different measured mechanism, not another repeat |
| Persistent virtual2 down | About 26 µs slower | Different scheduling mechanism |

Question: could exact-order expert scheduling save 30 µs per ordinary layer?
No: the common V4 winners saved 22.083/22.291 µs. Both byte windows passed
60/60. V4 logical-lane mapping is retained for packet53b; persistent arms
close here. [Full closeout and uncertainty](../../../../notes/2026-10-17-own-runtime-packet53.md#device-results--october-17-09150919-utc),
[hash-preserved receipts](evidence-copy/inventory.json). No model speed claim.
