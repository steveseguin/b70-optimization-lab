# Packet58ai: current one-card miss census

Preparation only. No queue or device launch is authorized by this packet.
The coordinator may schedule it only after both two-card queues are empty.
The record anchor is packet58ad, 30.396 tok/s, tile16, p60fusion, maximum
21,552,729,600-byte immutable expert cache, overlapped maintenance, zero-copy
misses, BF16 KV and the unchanged iq3-p49-split32-v1 oracle.

The complete tracked packet58ad copy is retained under lineage/packet58ad
and lineage, including symlinks. The root adapters derive from that copy;
the single-load bracket adapters come from its native parent, packet58ab.
The 148-file private native source closure is the source behind 58ad's
hash-bound 58ab executable. No old packet is modified. Immutable parent
object files are the only native build dependencies outside this tree.

The lab's packet58af partition mechanism is reused at its exact expert
kernel sites. This contribution is instrumentation, not a new optimization.
A0/A1/A2 disable profiling. B0 retains ordinary events around the ORIGINAL
mixed-residency launches. B1 measures disjoint resident and zero-copy
partitions on the same in-order queue, for every layer and position.
All five views use p60fusion and the same tile16/cache configuration.
Every view runs all 12 fixed prompts with a 128-token cap, in ONE load.
Each generated token is checked against the unchanged packet49 oracle.

Partitioning changes scheduling. B1's resident compute and miss service
are measured diagnostic intervals, not the original kernel's internal
stall cycles. B0 records the actual router-ready-to-expert-start window.
No subgroup-clock conversion is assumed: the installed experimental clock
has no portable time conversion or shared-device clock guarantee.
The analyzer must keep this distinction and report overhead against both
warm controls. These repeated views never supply a performance headline.

Event retention happens only when prepared commands are INVOKED, outside
capture. Queries happen after the existing token drain. Cache hit/miss IDs
are classified from the published pointer table and the existing route
readback, before cache observation changes. Fills are never counted as misses.

The final READY-FOR-DEVICE.json is written last and is the handoff authority.
Missing build, CPU quality, entry, pin, loader or report checks keep it false.
The diagnostic does not establish device equality or measured cost before it runs.

Retention: the requested source copy deliberately includes previously retained
archives/receipts over 1 MiB. lineage/58ad-copy.json identifies their original
bytes and commit; restore the tracked copy from Git. New build outputs are
ignored, rebuildable from build_engine.py, and capped at 300 MB. Preparation
uses nice19, helper cores, closed stdin, Python -B and at most 4 GiB.
