# Packet53 preregistration

Keep production expert arithmetic unchanged. No arithmetic-v3 oracle job.
The fixed candidate census is [manifest.json](manifest.json), five gate/up
arms and three down arms. Paired gate/up IQ2_S uses K=2560 and 640 rows per
expert; down IQ4_NL uses K=640 and 2560 rows per expert. Ten distinct expert
routes change between two fixtures and two token rows, with real production
compact-format strides. M=2 is two independent serial M=1 engine rows.

Gate/up: persistent global and persistent 8 KB SLM codebook (64 workgroups,
256 threads = eight SG32 per group); nonpersistent virtual2/virtual4 global;
combined persistent virtual2 SLM. Down: virtual2/virtual4 global and persistent
virtual2 global. Virtual lanes are separate original chains, never tile-split
multi-accumulators. Logical lane l visits 256*t+8*l, eight consecutive values,
then participates in the original adjacent binary reduction. No reassociation,
FMA, lower precision, changed weights or KV cache.

CPU checks must compare FP32 lane sums/tree results before BF16 rounding,
validate scheduling coverage and test the actual production-format traversal.
GNU and Intel host fresh repeats precede device admission. E1/E2 compare every
candidate output, route status and error byte to both the production control
and its CPU evaluation, with matching complete captures in two fresh owners.
T1/T2 wait for both E windows under the identical seal, boot and environment.
No first speed verdict before both fresh timing owners finish.

Each timing pair alternates control/candidate order across 210 iterations;
the first 10 are excluded. Save all 200 measured pairs and every regression.
For each class choose the same arm in both owners by maximizing the lesser
owner's M1 paired median saving (control is zero; names break ties). Sum the
two class savings. The bar is **at least 30 microseconds per ordinary M=1
layer in each owner**, never averaged across owners. M2 sums both serial rows
and is reported separately; it cannot rescue an M1 failure. This is an
operator screening decision, not measured model throughput or integration.

Coordinator alone owns card0, PCI0000:23:00.0, after its current work has
released ownership. Preparation launches no GPU, health probe, service or
oracle and never touches packet49c chain files. All preparation stays nice19,
cores4-15,20-31; one compiler/test owner at once; build below1GB. Use the
packet52 PF_EXITING-tolerant memory sensor and reject a future fault-review
boundary. Watchdog2880s covers four times the conservative12-minute T budget;
native cooperative deadline2820s leaves teardown time.

Planning estimates: E2–5min and T6–12min per window, conservative allocations.
Packet52 actually took about34s E and30s T; p53 has fewer comparisons and
may be similarly short, but persistent kernels have no device timing yet.
No claim of a multi-minute measured runtime is made.
