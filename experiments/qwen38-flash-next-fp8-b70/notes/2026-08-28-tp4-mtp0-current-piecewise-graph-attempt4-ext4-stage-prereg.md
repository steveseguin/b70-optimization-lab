# Qwen3.8 Flash-Next FP8 TP4 PIECEWISE MTP0 attempt 4 preregistration

Date: 2026-08-28
Status: frozen; not launched

## Why attempt 4 exists

Attempt 3 stopped before model launch or GPU work. Its temporary swap activated at
the frozen priority `-1`, but the mechanically derived inner supervisor resolved
its wrapper and client relative to its own USB `script_dir`; those files were not
present there. Cleanup passed and restored the original swap layout. The preserved
attempt-3 resource manifest contains 28 entries, verifies cleanly, and has SHA-256
`7f1abf63d1c57d14cacaf67eaad957ff2ecf85e467d717b3bbcf0a47f4e73fc3`.

The sole material runtime treatment in attempt 4 is to make the inner
`script_dir` self-contained on ext4. The outer supervisor creates the exact fresh
live directory `/var/tmp/q38-piecewise-graph-a4-resource`, derives the inner
supervisor there, and stages unchanged copies of the frozen wrapper and client
under the basenames the inner supervisor expects. All three live inputs must be
regular, non-symlink files owned by `1000:1000`, mode `0500`, with their frozen
hashes and stable device/inode/owner/mode/size identities. Those gates run before
the inner supervisor, throughout its lifetime, and at terminal adjudication. The
repo originals are never modified.

Because the wrapper itself is staged, it resolves its frozen base launcher by
the absolute repo path
`/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/tools/launch-tp4-ep4-piecewise-mtp0-4352.sh`,
not relative to the ext4 staging directory. The existing base SHA-256 gate is
unchanged.

The ext4 location is required because the attached NTFS/fuseblk volume presents
files as mode `0777` and root-owned, so it cannot substantiate the mode-`0500`
contract. The small live resource directory remains after the run as evidence.
The fresh USB archive destination
`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-piecewise-mtp0-4352-r1-attempt4-resource-archive`
is declared and freshness-gated for a separate post-closeout mirror; attempt 4
does not create, delete, or mirror it during runtime.

## Frozen identity

- port: `19678`
- inner state: `/tmp/q38-mtp0-current-piecewise-graph-a4`
- outer state: `/tmp/q38-mtp0-current-piecewise-graph-a4-swap64`
- swap: `/var/tmp/q38-piecewise-graph-a4-64g.swap`, 64 GiB, priority `-1`
- live resource/script directory: `/var/tmp/q38-piecewise-graph-a4-resource`
- run, cache, compile, RPC, and ordinary inner-supervisor evidence paths: fresh
  attempt-4 paths frozen in the supervisor
- model/runtime, PIECEWISE graph configuration, MTP0, request/quality/replay/speed
  protocol, 7,200-second lifecycle, resource floors, watchdogs, swap-traffic speed
  exclusion, journal gates, and exact cleanup contract: unchanged from the frozen
  attempt-3 packet

## Frozen files and hashes

- wrapper: `experiments/qwen38-flash-next-fp8-b70/tools/launch-tp4-mtp0-current-piecewise-graph-a4.sh`
  SHA-256 `11515e4980eacd58a4e156a0463029f0095dbec05bd8758ee582c23a15a85945`
- client adapter: `experiments/qwen38-flash-next-fp8-b70/tools/run-tp4-mtp0-current-piecewise-graph-a4-client.sh`
  SHA-256 `d7d3eae9415f4f5512612cfcf84362713749dca830ab28939e0223c069e5ec1d`
- watchdog: `experiments/qwen38-flash-next-fp8-b70/tools/watch-tp4-mtp0-current-piecewise-graph-a4-resources.sh`
  SHA-256 `9aa6ff18fde1006e8857901c7f81c64df56adf4c3fac82c34b32d3de0325c5b5`
- outer supervisor: `experiments/qwen38-flash-next-fp8-b70/tools/supervise-tp4-mtp0-current-piecewise-graph-a4-swap64.sh`
  SHA-256 `b1feab4ca3ece3285ea0ed7082f1671b283c9fa1cae4392f37debe771ef4f130`
- mechanically derived client: SHA-256
  `af47fee3ebb27a157ee78b88497a1a150e6b6ff904b598e3d706af36469c9c53`
- mechanically derived inner supervisor: SHA-256
  `50ca32aeac64432c6274f5963f8239f790bf9383737a90f5fde095337d5b73df`

Attempt 4 must not run until an independent read-only audit confirms this hash
chain, the ext4 staging contract, fresh paths, and the attempt-3-to-attempt-4
mechanical diff. Captured eager or graph speeds are protected and unchanged.
