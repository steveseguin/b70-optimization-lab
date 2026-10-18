# Packet137 — exact token-input path

## Preparation, October 18

The new copy uses packet124c bundle7. Packet136 was present but uncommitted at
entry, so it was not used. Pull refused because unrelated orchestration files
were dirty; fetch confirmed HEAD and origin/main both at
`871fd06e209b0ab09081ef3443e557b5626a8c92`. Root had 38.7 GB free.

All 182 parent symlinks are retained verbatim. The parent and other live work
are untouched. A read-only helper audited the original draft arithmetic and
launch gates while the host was busy.

Implementation is in progress. The new runtime has a full-vocabulary read-only
projection table path, bounded pinned draft row, and fixed target lookup buffers.
The original draft path uses the unmodified norm tree and 32-lane projection
sum. Target decoding hoists block setup without moving a rounding boundary.
Existing history and device rollback remain authoritative.

The table builder streams 5,120 bytes per vocabulary ID, checks target decode
bytes, then replays the original chain with the other compiler. A 32-row pilot
was submitted to the shared compiler turn. The whole-host marker was active;
no bypass is allowed. No successful table/build/runtime test is claimed yet.

CPU-only rules: nice19, CPUs 8–15/24–31, Python -B, stdin closed, CPU entry
address-space cap 4 GiB. Root must remain above 25 GB; builds below 300 MB.
Table budget is 1,271,398,400 bytes, outside Git. No GPU, service, sudo, host
setting, power setting, reboot, live queue or unrelated file changed.

## Full table and CPU parity milestone

Both GNU and Intel completed all 248,320 vocabulary rows with identical
bytes. The file is read-only at
`/home/steve/own-xpu-runtime-results/packet137-token-input/draft-embedding.bf16`.
Its SHA-256 is
`72260c77f4fec1174caead915453e0647e7b18d487255a114a8f96ae1e2709c9`
and its size is exactly 1,271,398,400 bytes. Generation streamed to disk;
maximum child RSS was 287,220 KiB. The complete receipt is
`experiments/own-xpu-runtime/stage2/packet137-token-input/evidence/table.json`.
The builder replays the original normalization/projection primitives and
checks raw embedding decode bytes. Intel verifies every GNU output row.

The target decoder passed all 65,536 FP16 scale bit patterns for both Q6_K
and IQ4_NL, including nonfinite values, under both compilers and fresh
repeats. The signed PLE/EOS/history test passed 4,096 cases per run.
The miniature native IPC replay preserved exact draft proposals, target
tokens and final state against the frozen parent and both compilers through
five views and fresh repeats. Full production-shape startup and reset
checks passed; these CPU mocks do not qualify device output or speed.

The initial GNU/Intel pilot exposed a missing Intel OpenMP runtime path;
the builder now embeds the library rpath. Its earlier failure log remains
under the build directory. An unchanged legacy K2 numerical fixture exceeded
the mandatory 4 GiB CPU cap. The cap was not raised. Its failure receipt is
retained, and the all-window gate uses the real K2 argument path and the
frozen measurement-validator replay. K0/K1a/K1b ran locally. K2 is explicitly
not claimed as a new successful numerical run.

The native review removed repeated mode lookups from the per-kernel loop
and restored transfer-time accounting for the direct staged row upload.
The final qualification is being rerun after those changes. Device proposals
will require the 32-row original-device-chain check before readiness, exact
target output, identical per-prompt proposal sequences and acceptance across
the bracket, and the original oracle binding. No GPU was used.
