# EX400U ordinary-I/O review and additional research backup

The owner authorized proceeding with backup investigation after confirming that
RAM replacement is deferred through 2026. Existing memory exclusions remain
unchanged. This review performs no SMART passthrough, firmware update, filesystem
repair, driver reset, host restart, power-setting change or GPU workload.

## What the incident establishes

The saved October 6 kernel log first reports a failed vendor command, opcode
`0xe6`, immediately after the `smartctl -d sntasmedia -a` query. An ordinary read
later timed out, followed by a kernel-initiated USB reset and read error. This
supports a passthrough-trigger hypothesis; it does not prove media health or
establish that the bridge command was the only cause. The SMART report's enormous
power-cycle/hour counters make its overall health claim unsuitable as a gate.

The separate August NTFS mirror mismatch remains historical evidence. The
drive-local health note still calls for Windows filesystem maintenance; this
review does not establish that it happened. A successful mount is not a full
filesystem check.

The saved report identifies firmware ULFM91.0. Corsair documents a disconnect
problem on some EX400U units with that firmware, but the exposed USB serial does
not match the advisory's serial format/range, so applicability is unconfirmed.
The vendor's reinitialization procedure **erases all user data** and requires
Windows; it was not attempted. [Corsair advisory](https://help.corsair.com/hc/en-us/articles/39222145509137-How-to-Fix-EX400U-Drive-frequently-disconnecting).
Corsair separately lists ULFM91.2 fixes for a specific USB-port compatibility
issue and displayed health information. Those notes do not establish that it
fixes this Linux incident. [Official release notes](https://www.corsair.com/us/en/explorer/release-notes/ssd-firmware/ex400uex400u-survivor-ulfm912/).

## Bounded pilot and inward preservation

Identity: Corsair EX400U, USB `1b1c:1a20`, NTFS partition UUID
`4E0E66ED0E66CD91`, mounted through `ntfs-3g`. The initial empty mountpoint and
UUID were checked before a single `ro,norecover` mount. No recovery option or
force mount was used. Later mounts also used nodev/nosuid/noexec.

The Flash-Next configuration and index matched independently recorded hashes.
Beginning/end ranges from two known model shards matched their internal copies,
128 MiB total external model data. This is sampled read evidence, not full-model
verification. No new kernel storage errors appeared.

Four exact Flash-Next A367/A394 run and supervisor directories existed only on
the external drive. Their 121 files (14,340,909 bytes) were copied into
`/home/steve/git-archives/flash-next-rescue-20261007/`, every destination was
SHA-256 compared with its source, and source files were retained. This preserves
their current bytes without requalifying historical benchmark correctness.

After clean unmount, a single `rw,norecover` mount accepted an additive write
pilot in a new backup directory. A 95,389,557-byte preserved cache archive was
copied and fsynced. Another clean unmount/read-only remount preceded its complete
SHA-256 read-back; it matched, and the kernel log remained clean. This justified
an additional-copy attempt while retaining every internal original.

## Backup scope

Destination: `/mnt/usb-models/lab-backups/steve-b70s-20261007/`.
The Git bundle and tracked worktree snapshot capture commit
`8172add663bf29c842129d366ab422df3355b04b`; final review receipts are recorded
separately. The tracked archive is checked against Git blob identities, avoiding
incorrect comparison of archive commit timestamps with working-file timestamps.

The frozen research selection contains 404,095 paths: 348,263 regular files,
55,830 directories and two preserved symlinks. Regular-file payload totals
65,984,476,250 bytes (61.45 GiB). It includes:

- the existing consolidation archives, historical Git bundles and inward rescue;
- mistake/recovery ledgers and the LTX application source;
- LTX prepared packets, source snapshots, requests, logs and fault evidence;
- 36 exact reference-output directories and all 2,618 packet-97 output directories;
- other LTX previews outside the validation tree.

It excludes model stores, LTX quarantined model copies, other validation outputs,
the repository's ignored diagnostic models, home credentials and session folders.
This is not a whole-machine or complete raw-output backup. All omitted and
included original data remain in place. Symlinks are archived without following
their targets. Filename screening found no secret-like filenames; this is not
a content audit of every historical log.

The NUL path list and selection checksum prevent accidental recursive inclusion
of unrelated sources or newly created backup files. Source byte comparisons and
a complete archive-member census are required before accepting the archive.
Completed files must then survive a clean unmount/read-only remount and full
SHA-256 read-back. Kernel errors stop new backup I/O; no retries are scheduled.

## Completion

**Completed October 7 at 01:00 UTC; drive cleanly unmounted.** Nine backup files
total 27,523,871,235 bytes (25.63 GiB), including the compressed research archive,
Git bundle, tracked snapshot, pilot archive, complete selection and restore/checksum
controls. All nine SHA-256 hashes matched after clean unmount/read-only remount.
The research archive passed full source comparison and the complete 404,095-member
census. The Git snapshot matched all 44,387 tracked blob identities.

The bundle was restored into a disposable bare repository; its HEAD matched
the recorded source commit and `git fsck --full` passed. The packet-98 manifest
and recovered output-size helper were extracted from the external research
archive into a disposable directory and matched their pre-existing pinned hashes.
Temporary restore-check directories were removed. Final kernel/mount postflight
passed, with no new storage/GPU faults. Internal available space was
57,758,072,832 bytes (53.79 GiB); all internal originals remain intact.

One orchestration preflight was invoked while the clean-remount command was
still finishing. The missing-mount guard refused it before worker launch or
backup reads. After waiting for that existing command to complete successfully,
the verification worker ran once. No mount retry or storage-fault recovery was
performed; [the event receipt](../data/maintenance/backup-review-20261007/readback-preflight-event.json)
preserves the correction.

All machine-readable receipts, including [the completion summary](../data/maintenance/backup-review-20261007/summary.json)
and [full verification](../data/maintenance/backup-review-20261007/verification.json), are under
[`data/maintenance/backup-review-20261007/`](../data/maintenance/backup-review-20261007/).

Regardless of verification outcome, the result is an additional copy on a
different physical drive, not proof of long-term EX400U reliability. Preserve
the internal sources and keep this drive out of active model/runtime paths.
