# Packet58ae — measurement preparation, October 18

The requested pair of device measurements is **not ready**. The packet has a
compiled cache-publication split, sparse mixed-expert event instrumentation,
a read-only analyzer, a combined proposal and passing CPU report/planning
checks. The second arm cannot yet separate miss stalls from resident-slot
compute or measure their overlap window. Those values remain unknown, and
the entry refuses device execution. No result or speed claim changed.

The [packet README](../experiments/own-xpu-runtime/stage2/packet58ae-onecard-measure/README.md)
records the exact implementation, decision rules, restoration commands and
remaining work. The [final marker](../experiments/own-xpu-runtime/stage2/packet58ae-onecard-measure/READY-FOR-DEVICE.json)
is the handoff: `ready_for_device=false`, written last.

Arm 1 records host packing, H2D/scatter device events and the existing host
wait without adding token waits. The two on views switch queue profiling on
at a drained view boundary; off controls switch it off. This makes the future
overhead comparison include profiling itself. Its required <2% result is
pending device evidence, not proven during CPU preparation.

Arm 2 gets hit/miss bytes from the existing route readback and samples one
rotating layer's two expert-site tail events per generated token. Those events
contain resident and host-backed work together. Light event boundaries cannot
separate their subgroups. Labeling the whole duration as miss stall would
mislead packet147's transfer ranking and the M2 verifier decision. A separate
slot-timing mechanism must be implemented and qualified before readiness.

CPU results: both compilers pass; unchanged objects relink to packet58z's
exact host/device binary hashes; both five-view miniature repeats preserve
all retained layer bytes and output tokens; a wrong oracle fails before B0.
The shared native-entry/report rehearsal passes, with no imported-module
collisions. Analyzer/admission tests and a temporary lane-A queue plan pass;
the pin guard passes. These do not replace the changed engine's remaining
full-size startup and real queue-to-native launch checks.

The combined proposal budgets <=900 seconds for both arms in one model load,
with 3,600-second watchdogs and the existing packet58ab whole-host hold.
It is clearly blocked and remains unqueued. It retains the frozen tile16
selection, max cache, overlap, BF16 KV and packet49 arithmetic/oracle binding.

Only the new packet, this note and its new proposal were changed by this work.
Existing packets, screen wrappers and ops code were kept frozen. No model or
full-shape payload was read, and no GPU, service, sudo or host setting was
used. Compile turns went through the shared CPU gate with nice19, helper
cores, stdin closed and a 4 GiB address-space cap. Root stayed above 25 GB;
the retained build is below 300 MB. Unrelated dirty orchestration and CURRENT
changes belong to other work and are not included in this commit.

The 12.2 MB vendored source archive is intentional reproducibility evidence.
It restores expanded source trees without consulting mutable parent code;
new native binaries remain ignored. The source-copy manifest preserves
original file hashes and symlinks. No unmeasured numbers are published.
