# Flash-Next TP4 eager MTP0 fixed-vision attempt 9 result

Date: 2026-08-28
Status: bounded host-swap negative during model loading; no vision, quality, speed, matrix, or website credit

Attempt 9 passed its administrative 105-GiB MemAvailable admission treatment,
the 900-second user-manager recovery window, four-card and XCCL health, IPC
path, and schema-v3 runtime gates. The exact TP4/EP4 eager MTP0 vision server
then started loading the 131-shard checkpoint. It reached only `5/131` shards;
no rank completed model loading and the API never became healthy.

The last sample above the frozen active-run swap floor was at 14:45:22:
21,955,644 KiB MemAvailable and 5,433,272 KiB SwapFree. At 14:45:24,
SwapFree fell to 3,414,672 KiB, 1,828,208 KiB below the 5-GiB floor, while
MemAvailable remained 23,995,596 KiB and therefore stayed above its separate
10-GiB floor. The supervisor wrote the exact resource-failure receipt and
terminated the owned launcher. Child and final supervisor rc were both `143`.

This is Grade-D host-resource evidence for the exact attempt-9 identity. It
does not classify Flash-Next vision capability: `health.json` is empty, the
client never ran, and there is no same-boot text recovery, semantic case,
fixed-image request, quality result, deployment result, or speed row. An
identical retry is not justified; a successor requires a materially different,
preregistered host-memory or swap treatment with fresh paths and identity.

Postflight was clean. Port 19688, the server group, model workers, compile root,
and RPC root are absent. The final schema-v3 runtime scan is clear with zero
conflicts, errors, or vanished races across 550 scanned processes. The kernel
journal contains only the expected `drop_caches` receipt and no OOM, killed
process, TTM/eviction, RxErr, or B70-addressed event. System and user managers
are running, there are zero failed system units, both Muse Glimmer services are
inactive, and the recorded four-card
memory is `42.8828125 / 42.875 / 42.875 / 42.87109375 MiB`.

Raw evidence remains in the attempt-9 run and supervisor directories. They
contain 16 and 70 files respectively; the 31-entry prelaunch
`admission-recovery.sha256` verifies. The tracked combined manifest binds all
86 immutable files, verifies from the raw family parent, and has SHA-256
`c7daeced21a50cdf7fae02531b845fec4dd17ccdb98b495a4e9b3faffd947b06`:
[`20260828-tp4-mtp0-fixed-vision-attempt9-primary-evidence.sha256`](../data/20260828-tp4-mtp0-fixed-vision-attempt9-primary-evidence.sha256).

This closeout changes no family, package, matrix, site, or captured eager
speed. The protected family, result README, and handoff hashes remain exactly
`c378b6f584235632d5fe8d178bc756be6c6ff12309ba5ec352a9cd1369e9254d`,
`deb1869104c941cf784594d0bb6c8e3d1e7523075ed74d54a80f930413360a7d`,
and `51eb4714f9f4050fd4d49a906ee2f7e2ae83fcc081218244756812ed7cc9f63f`.
The structured receipt is
[`20260828-tp4-mtp0-fixed-vision-attempt9-result.json`](../data/20260828-tp4-mtp0-fixed-vision-attempt9-result.json).
