# Qwen3.8 Flash-Next TP4 MTP0 PIECEWISE graph attempt-2 preregistration

Date: 2026-08-28

## Decision and bounded authority

Attempt 1 is a bounded host-memory admission negative: all four ranks loaded the
frozen model and began PIECEWISE compilation, then the host exhausted its
ordinary 8-GiB swap. The kernel terminated rank 3 at 10:23:25 EDT. There was no
health response, model request, quality result, or speed result. The exact
closeout is in
`data/20260828-tp4-mtp0-current-piecewise-graph-attempt1-result.json` and the
41-entry raw-evidence manifest has SHA-256
`ffc849c14bd36a66f638953f6d668d55fc61599674d85caec676c0671b964231`.

Attempt 2 is authorized as one boot and, only after health, the unchanged
attempt-1 client protocol. Its sole material treatment is one temporary,
fully-allocated 64-GiB swapfile on the root ext4 filesystem. The model,
revision, current vLLM and kernel overlay, TP4/EP4/MTP0 placement, PIECEWISE
configuration, 192-MiB KV cache, request order, quality oracle, replay gate,
three short rows, and all captured eager speeds are unchanged. A negative is a
classification result; it is not evidence that any retained speed regressed.
No production or LocalMaxxing claim is authorized.

## Frozen identity and paths

- graph base SHA-256: `533be64e1c7584448c07a5f8895301a32288f4b0472948a91d87235e78c6f09f`
- attempt-2 wrapper: `launch-tp4-mtp0-current-piecewise-graph-a2.sh`,
  `6ac73fbef6c98242d2e8f793ce56ecc918fc32b41bd1f00c06d7374f2cbe4ac9`
- client adapter: `run-tp4-mtp0-current-piecewise-graph-a2-client.sh`,
  `b1962a6e2956dba06215aa5ac966ae04a771d7fb1407c9444605d275a817047d`
- derived client SHA-256:
  `6f2888348f62955a0f64ce1621c7546e9ace0000cfa6ca179e20979b020710c0`
- resource watchdog: `watch-tp4-mtp0-current-piecewise-graph-a2-resources.sh`,
  `fe0723bff6c1afa40b7cae450f55270c3489bcb33bec96126daa6743161e1bc2`
- outer supervisor: `supervise-tp4-mtp0-current-piecewise-graph-a2-swap64.sh`,
  `da9a053e9f706c29845ab519fe68760e6d86b02b6e8be76847044c3e2b52382d`
- mechanically derived descendant-aware supervisor SHA-256:
  `88fc287124c7eeae7b8dfc49b2407fcf02ac2d1f23ca29aee5e46a3fd8c11084`
- attempt `2`, port `19675`, state
  `/tmp/q38-mtp0-current-piecewise-graph-a2`
- fresh run/cache/compile/RPC paths end in
  `qwen38-flash-next-fp8-tp4-ep4-piecewise-mtp0-4352-r1-attempt2`
- resource evidence is isolated at the same campaign suffix plus `-resource`;
  the ordinary descendant supervisor evidence ends in `-attempt2-supervisor`
- temporary swapfile:
  `/var/tmp/q38-piecewise-graph-a2-64g.swap`, exact size 68,719,476,736 bytes
  and expected `/proc/swaps` size 67,108,860 KiB

The adapters hash the frozen attempt-1 client/supervisor sources and perform
only declared attempt, path, port, wrapper/client-hash, and measured-row
resource-gate substitutions. Their derived bytes are hash-gated before use.

## Resource admission and continuous stops

Before any host mutation, require `/var/tmp` to resolve exactly to the writable
`/dev/nvme0n1p2` ext4 root filesystem, the target path to be absent and
inactive, all attempt-2 paths to be fresh, and at least 111,669,149,696 bytes
available (64 GiB plus the 40-GiB retained floor). The existing swap layout is
saved without its mutable `Used` column.

The supervisor authenticates through the protected local sudo file without
printing it. It creates a mode-0600 file without overwriting any existing path,
binds its device/inode before privileged work, makes it root-owned, and then
fully allocates it with `fallocate`. Every privileged setup call is bounded to
180 seconds. The active file must remain a regular non-symlink root-owned
mode-0600 file whose allocated blocks cover its full logical size, and the
supervisor records identity after creation, after `mkswap`, before `swapoff`,
and after `swapoff`. The pre-existing swap layout must remain unchanged when
the new exact row is added.

The one-second watchdog records `MemAvailable`, total/free/used swap, temporary
swap size/use, root availability, `pswpin`, `pswpout`, and memory PSI some/full
avg10. Its heartbeat must never be older than ten seconds. Any of these stops
the arm prospectively:

- root availability below 40 GiB;
- `MemAvailable` below 12 GiB;
- the combined state `MemAvailable < 16 GiB` and `SwapFree < 8 GiB`;
- memory PSI full avg10 at least 5.0 for 30 consecutive samples;
- temporary swap missing or changing size;
- a new kernel OOM record or `RxErr` in the attempt-2 window;
- unreadable resource/journal input, watchdog exit, or stale heartbeat. These
  faults are latched by the outer supervisor, terminate the inner arm, and
  force final failure even if a valid client stop races with the fault. Final
  status also requires the watchdog's controlled-stop receipt and a terminal
  heartbeat no older than 15 seconds, closing the inner-exit boundary race.

The fixed request gates remain recovery canary, frozen 6/7 semantic state with
exact eager-a4 parity, alternating 96/96 color plus 96/96 JSON exact replay,
positive runtime PIECEWISE evidence, and then the three p146/o256/c1 short
rows. Each measured row now snapshots `pswpin`, `pswpout`, temporary swap use,
and PSI at its boundary. A nonzero paging-counter delta or any increase in the
temporary file's used pages fails before the PASS/stop sentinels, so a
paging-contaminated row cannot receive speed credit.

## Lifecycle and teardown

The inner graph lifecycle retains its 2,700-second boot bound and 7,200-second
descendant-aware bound; the client still refuses to start with less than 3,900
seconds remaining. The outer 7,500-second bound covers model/inner occupancy,
not subsequent swap cleanup. After a stop or TERM, the outer supervisor allows
at most 360 seconds for inner descendant cleanup. If that bound is missed, it
forces a failed result and preserves the active temporary swap rather than
removing memory backing under a live process. The temporary swap otherwise
remains active until the owned graph server and descendants have completed
cleanup.

Teardown admits `swapoff` only when `MemAvailable` exceeds temporary swap use
by at least 16 GiB. `swapoff` has a 900-second TERM/KILL bound. Device/inode,
type, ownership, size, mode, and allocation are rechecked around it. Only after
successful `swapoff` may the exact path be removed with `unlink`; the original
swap layout must then be restored exactly. If safe swapoff or identity proof is
unavailable, the supervisor deliberately preserves the active file, records a
cleanup failure, and returns nonzero rather than risking another host-memory
incident.

## Prepared commands

These commands have not been run:

```bash
/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/tools/supervise-tp4-mtp0-current-piecewise-graph-a2-swap64.sh
/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/tools/run-tp4-mtp0-current-piecewise-graph-a2-client.sh
```

Do not start until an independent read-only audit confirms the hash chain,
fresh paths, current root headroom, idle cards, and cleanup semantics.
