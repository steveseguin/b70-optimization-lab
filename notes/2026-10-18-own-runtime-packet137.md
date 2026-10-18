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
