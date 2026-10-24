# One fixed IQ4_NL down comparison — source preparation

No extraction, native build, operating plan or device execution has occurred.
The parent CPU proof passed13,193 exact address/arithmetic checks in root's run;
its source files remain frozen. This subdirectory prepares the next separate
qualification, not a replacement for the prior IQ3 micro's failed physical gate.

`prepare.py` derives `runner.cpp` from the preserved IQ3 paired-micro lifecycle.
The explicit diff changes to one layer0 IQ4_NL down case, original p6 control
versus the exact parent `direct.hpp` candidate, and an acknowledged backend-start
phase. Both operators use all ten original per-slot inputs, 512 expert IDs,
N2560/K640/span2560, BF16 input/output and four SG32 subgroups. Four excluded
warmup cycles and24 measured cycles alternate AB/BA:28 exact pairs/56 kernels.
Every pair compares all51,200 output bytes and40 status bytes to each other and
the original saved baseline, with no filtering or tolerance. Timing queries
remain before retirement. No flush, alternate precision or cache-control change.

One sparse full-shaped weight bank is471,859,200 bytes. Device buffers total
471,974,600 bytes; transfer operations total474,741,560 bytes, with a separate
1MiB pinned slab. The sparse CPU backing is the same bank size. Only consumed
expert slices are populated, at their original expert IDs. All others are zero
and may not be referenced by any valid nonempty original route.

`extraction-plan.json` identifies the fixed archived original prompt00 target
capture. The original graph has one writer for each of input `blk.0.expsact`,
route `blk.0.routes.down`, output and status. Four original member hashes/lengths
cover64,160 bytes. Extraction would verify the fixed90,040,912-byte compressed
archive, stream its bounded231,442,500-byte contents without unpacking arbitrary
paths, and retain only those four members. At most ten921,600-byte model expert
slices would then be read after held-FD/header/stat authentication. No full-bank
or whole-tensor payload hash is claimed. The extractor is a plan here; it is not
implemented or authorized to read payloads yet. A real `fixed.hpp`, successful
extraction receipt, native build and independent review are required before the
coordinator can form a plan; no placeholder fixture header is supplied.

`startup.hpp` waits after real `make_sycl_device` construction and ownership by
`Device`. The frozen backend creates its actual Level Zero context and in-order
profiling queue in its constructor and retains them until explicit shutdown.
There is no synthetic admission DRM descriptor. Before allocations, uploads,
capture or candidate/control kernels, the child publishes PID/startticks plus a
random challenge and waits up to60 seconds. A cooperative signal or deadline
throws into the unchanged positive backend synchronization and Device shutdown
path; uncertainty still holds for the supervisor. Teardown may submit its normal
idle marker; no benchmark kernel is allowed before ACK.

`once.py` is a draft derivation of the same passive coordinator. It grants ACK
only after an entire current sample passes all inherited unit/PID/boot/fault/
application/coordination/memory checks and records the native PID's actual target
DRM holders. The exact accepted sample is durable before ACK publication. The
child checks the exact challenge and identity, a stable regular single-link
ACK and its current path. Parent terminal success additionally requires both
ACK and the unchanged positive physical contact/clean drain gates. If queue/
context construction does not expose a persistent target descriptor on this
driver, the wait refuses; this source does not assert an unobserved FD exists.

Ready and ACK are atomically published without replacement using renameat2 on
the fixed NVMe result filesystem. The coordinator requires that device identity
match the repository filesystem. This is deliberately not the NTFS evidence
volume that rejected renameat2 in the state-bundle pilot. The exact publication
and absent/stale/wrong ACK branches still need bounded CPU tests and review.

`runner.patch` and `once.patch` preserve the parent-to-candidate changes. Existing
error retention, one cooperative stop attempt, no retry, safe owner shutdown and
hold-on-uncertainty behavior remain. Root owns all future read/build/device
admission; current coverage measurements prohibit concurrent compile/payload I/O.
