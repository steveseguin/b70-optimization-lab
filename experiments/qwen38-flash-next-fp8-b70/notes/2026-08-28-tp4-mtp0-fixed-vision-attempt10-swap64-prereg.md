# Flash-Next TP4 eager MTP0 fixed-vision attempt 10 preregistration

Date: 2026-08-28
Status: frozen packet; not launched

## Why this arm exists

Attempt 9 passed its 105-GiB admission gate and began loading the exact eager
vision server. It stopped at 5/131 checkpoint shards when live `SwapFree`
fell from 5,433,272 KiB to 3,414,672 KiB, below the frozen 5-GiB active floor.
At the trip sample `MemAvailable` was still 23,995,596 KiB, above the frozen
10-GiB floor. The API never became healthy and no client, text recovery,
vision request, quality gate, speed row, matrix credit, or website credit ran.

This packet binds both finalized attempt-9 artifacts before any resource or
GPU work:

- result SHA-256:
  `a23825dffb6edf7238744c60e7d28480bbc9e95b5c76fa62c01675e8743331d7`;
- 86-entry primary-evidence manifest SHA-256:
  `c7daeced21a50cdf7fae02531b845fec4dd17ccdb98b495a4e9b3faffd947b06`.

## Sole treatment

The sole material treatment is a temporary, fully allocated 64-GiB swapfile
on the root ext4 filesystem, activated at priority `-1` before the unchanged
attempt-9-derived inner supervisor starts. The precreation gate requires the
64-GiB allocation plus a 40-GiB remaining-root floor; the postcreation root
floor remains 40 GiB. The inner supervisor's root admission is correspondingly
40 GiB because the outer layer has already allocated the treatment file.

The serving, quality, and request identity is otherwise unchanged: current
model revision and runtime, TP4/EP4, eager MTP0, selective UVA placement,
201326592 KV-cache bytes, max-model-len 512, one image and zero videos per
prompt, zero multimodal processor cache, encoder TP weights, same-boot exact
`OK`, seven semantic cases, and nine fixed vision requests. This remains a
bounded capability/quality arm with no speed or deployment credit.

The live resource floors remain exactly those used by attempt 9:

- `MemAvailable >= 10 GiB`;
- total `SwapFree >= 5 GiB`.

The outer watchdog records temporary-swap use, paging counters, PSI, root
space, and the bounded kernel-journal window. It also stops on the exact live
floors, sustained full-memory PSI, the 40-GiB root floor, memory allocation or
eviction failure, OOM, a B70-addressed event, or an event the frozen block
classifier cannot safely attribute. A corrected/nonfatal root-NVMe event alone
retains the established graph-attempt-7 policy.

## Lifecycle and cleanup

The attempt-9-derived inner lifecycle remains 15,000 seconds and still
requires at least 10,500 seconds before client work. The outer lifecycle is
16,200 seconds, leaving a bounded cleanup margin. The outer layer reuses the
proven graph-attempt-7 controls: exact PID/start-time/command binding,
structured runtime scans, heartbeat freshness, direct owned server-process-
group TERM followed by a monotonic 12-second KILL threshold, and bounded
controller/watchdog shutdown.

Swap cleanup is fail-closed. Before any swapoff, the terminal server group and
structured runtime absence must both be clear. Swapfile device/inode,
owner/mode, size, and allocated blocks must remain exact. `MemAvailable` must
cover current temporary-swap use plus a 16-GiB reserve. Swapoff has a
900-second outer bound; only successful swapoff permits exact `unlink --`.
The original `/proc/swaps` layout must then compare byte-for-byte. An
unresolved process, identity change, unsafe reserve, or failed swapoff leaves
the temporary swap active and preserved for recovery rather than removing it.

System and user managers must be running with no failed system units, and the
user manager must have been continuously active for at least 900 seconds
before treatment. Final evidence requires the same user-manager activation
epoch and clean manager states; the packet never restarts or modifies those
services.

## Fresh identity

- attempt: `10`;
- port: `19689`;
- inner state: `/tmp/q38-mtp0-current-vision-a10*`;
- outer state: `/tmp/q38-mtp0-current-vision-a10-swap64*`;
- compile/RPC roots: `/tmp/q38v-a10-c` and `/tmp/q38v-a10-r`;
- ext4 resource root: `/var/tmp/q38-vision-a10-resource`;
- ext4 swapfile: `/var/tmp/q38-vision-a10-64g.swap`;
- USB run/cache/supervisor paths: exact `attempt10` successors;
- declared post-closeout archive: exact `attempt10-resource-archive` successor.

Every target path must be absent. No attempt-9 path may be overwritten.

## Frozen hashes

| Artifact | SHA-256 |
|---|---|
| `tools/launch-tp4-ep4-eager-mtp0-vision-512-base.sh` | `487f088481c0c7f5e821bdce7dda41bb20aa0761c4453215a0662f23473beb46` |
| `tools/launch-tp4-mtp0-current-vision-a10.sh` | `4e54eb348f76e889de3fe28403addc484e70a1dac6299ceff68c8dbb262de5af` |
| `tools/run-tp4-mtp0-current-vision-a10-client.sh` | `1c096de3a0c94a37941517a97700100451b7347f305849490e7d8f2de9972add` |
| `tools/supervise-tp4-mtp0-current-vision-a10-inner.sh` | `202bd61356347fbc49151f794a2b9a3aca7c4d827bb423c7aa1955916358099e` |
| mechanically derived ext4 inner supervisor | `94a484e3392c4126a5ae9e7a4da07dde9ff2c48d0b4889a4e9fcb3cf9f949907` |
| `tools/watch-tp4-mtp0-current-vision-a10-resources.sh` | `893d3cff3bddee78d580d92410f24d60cb8ffb5b77c1ccb527922131e0825057` |
| `tools/test-q38-vision-a10-resource-policy.sh` | `9c3af8906fe70eb79919cadc39a4bca8d470453ee3261cc91d5cbc17f5ddb506` |
| `tools/supervise-tp4-mtp0-current-vision-a10-swap64.sh` | `44d8a826185e2f51f0eb733ec777b7b5529b36ce2723e3c3a8110ff6c385f93e` |
| `tools/classify-q38-runtime-conflicts.py` | `ecd18d133eef946bacf2750717bc458eca8e64dc1d97beabe060bdf314bf2ab3` |
| `tools/test-q38-runtime-conflict-classifier.sh` | `c30a1d552388c10df0e61f882b633cf57304fd76e40eadc886676b78b27ff63e` |
| `tools/classify-q38-piecewise-graph-a5-kernel-journal.py` | `440d7d0636bef8b5baf9bd5603ced988e22fe64c7df912ed15e55561aea8ea16` |

## Launch gate

This note does not authorize launch. Independent review must recheck the full
hash chain, executable modes, A9 receipt predicates, derived-supervisor bytes,
fresh paths, current manager stability, root allocation floor, swap layout,
runtime ownership, four idle B70s, journal window, and the static resource
fixture. The only eventual entry point is the no-argument
`supervise-tp4-mtp0-current-vision-a10-swap64.sh`; direct wrapper, client,
inner-supervisor, watchdog, or derived-script invocation is not authorized.
