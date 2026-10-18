# Packet58ag: one-card target refinements

Started 2026-10-18 at 23:06 UTC; three-hour limit. Pull refused pre-existing
dirty orchestration files. Fetch confirmed HEAD and origin/main both at
`34423d4cfdf3f81f5277c96f1dbbee54491cf28d`. Root had 31.1 GB free.

The private symlink-preserving packet58ab copy adds HC-wide, wide64 expert
geometry, exact half-scale caching, packet109's target fusions and ordered
foreground retirement as runtime choices. HC fusion
stays on. The half-scale cache is a 256 KiB table covering every FP16 bit
pattern, preserving the existing packed weights and one-card cache layout.
The literal packet90 larger-row layout is not used. Packet109's fused router
includes exact route-fast; no standalone packet58r rerun is proposed.

The [audit](../experiments/own-xpu-runtime/stage2/packet58ag-onecard-ports/AUDIT.md)
records the other two-card selections and their exclusions. The original
rank1 retirement shortcut needed a separate one-card proof: the port tracks
both foreground queue terminals and leaves maintenance ownership alone.
Head splitting requires two devices. CPU tests and compilation
use nice19, cores 8–15/24–31, closed stdin and at most 4 GiB. Compilation uses
the shared turn gate. No GPU, service, model payload or live queue is touched.

Source milestone `e8e825cab` was pushed immediately. All new choices default
to production and switch only after draining and quiescing at a bracket
boundary. The historical `p60fusion` bracket token selects the full
composition here; both its control and candidate keep HC fusion enabled.

The device proposals are a 12-prompt × 64-token full-composition smoke, then
one load containing five 12 × 128 views: baseline/full/baseline/full/baseline.
The first view is exactness evidence and cache warm-up, excluded only from
the speed/drift comparison. Both candidates must beat both warm controls by
2%, with at most 3% warm-control drift. They reserve lane A and the whole
host. They are proposals only and are never inserted into live queues here.

CPU preparation covers both compilers' exact intermediate/output/status
bytes at real HC, expert and fused-epilogue shapes, fresh-process repeats,
all 65,536 FP16 scale bit patterns, actual capture/reset, all independent
choices and the composition. Sparse full-shape mocks exercise 16 switches
per check, contexts 32 and 4096, serial and overlap maintenance, unchanged
arenas and unchanged cache capacity. Ordered retirement is tested with
delayed compute/copy completion and separately owned maintenance work.
These are synthetic CPU proofs, not full-model device equality or speed.

The composed plan has 1,057 commands per half versus 1,345 in the baseline.
The reduction includes the original one-card router's multiple launches.
The half table adds 262,144 device bytes and 524,288 conservative host bytes.
It is charged within the existing 1 GiB workspace allowance; cache capacity
and the total device admission bound do not change. The full-shape mock
binds 27,841,904,372 device bytes. Host admission becomes 98,990,252,032 bytes.
No host memory settings changed.

CPU fixture fixes retained in this copy: post-load allocation testing needs
the table's upload slab; its allocation/copy expectations now count the table.
The Intel retirement test needed the already-pinned library search path for
libiomp5. Neither failure involved a GPU. Historical copied admission and
manifest references were relocated to this vendored closure; their original
bytes remain in lineage. The unchanged shared pin guard checks the result.

See the packet's [CPU closeout](../experiments/own-xpu-runtime/stage2/packet58ag-onecard-ports/CPU-PREPARATION-CLOSEOUT.md)
for retained receipts and exact pending device gates. READY is written only
after final seals, shared report rehearsal and both temporary queue plans.
