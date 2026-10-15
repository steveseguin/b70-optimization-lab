# Disk cleanup, 2026-10-15 about 13:45 UTC

Packet 45 SPEED4 chains (`eabc13242`) were refused twice at K2 storage admission before device contact:

1. 13:29: the `build/` budget was exceeded by parked result trees. They were moved out of `build/` to `/home/steve/own-xpu-runtime-results/packet45/`.
2. 13:38: root free space was 21.37 GB, against the free floor (8 GB) plus the remaining chain reserve (11.49 GB) plus the 2.5 GB K2 projection.

Moving the results to `/mnt/raid-models` failed: `/dev/sdb2` returns Buffer I/O errors (logical block 36; kernel log 2026-10-15 09:39 local), and mkdir/ls fail with "Input/output error". The raid mount was left untouched for the owner to inspect.

Removed (ignored, regenerable build output in finished packets, matching the 2026-10-12 precedent; nothing tracked, no receipt):

- `packet38-integrated/build/asan` (674 MB)
- `packet40-suite/build/asan` (1,016 MB)
- `packet38-integrated/build/fusion-fixtures`, `packet40-suite/build/fusion-fixtures`, `packet36-draft/build/fusion-fixtures` (about 202 MB each)

Root free went from 21,394,046,976 to 23,799,959,552 bytes. Kept: packet17 sealed `wa-reference`, the packet44 record and control chains, the packet45 `incident-*` and `speed3-*` record evidence.
