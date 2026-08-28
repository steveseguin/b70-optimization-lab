# Qwen3.8 Flash-Next TP4 MTP0 PIECEWISE graph attempt-3 preregistration

Date: 2026-08-28

## Decision and sole treatment

Attempt 2 stopped before the inner supervisor, model, collective, GPU load, or
request protocol began. The temporary 64-GiB file was fully allocated and
activated, but this host's util-linux accepts swap priorities only in the range
`-1..32767`. The frozen `swapon -p -2` request therefore appeared in
`/proc/swaps` and the kernel journal as priority `-1`; the attempt-2 exact
priority gate expected `-2` and stopped. Descendant state was never created,
the swap was safely disabled, the exact file was removed, the original swap
layout was restored, and final cleanup passed.

The preserved attempt-2 resource directory is:

```text
/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-piecewise-mtp0-4352-r1-attempt2-resource
```

Its 23-entry `raw-manifest.sha256` has SHA-256
`75effdc56560bd2322d6e34de8b4d9125d534f774c8761efe40f0b3383a2f5a8`
and re-verifies completely. The recorded kernel line reports exact size
67,108,860 KiB and priority `-1`; `swap-cleanup.log` reports the inactive exact
file removed, and `swaps-restored-layout.txt` matches the pre-attempt layout.

Attempt 3 changes exactly one material setting: request and require the
accepted priority `-1`. All graph, model, runtime, placement, cache, quality,
replay, measured-row paging rejection, resource watchdog, cleanup, and
interpretation rules remain byte-equivalent to attempt 2 after administrative
attempt/path/port/hash substitutions. This remains one bounded boot and one
unchanged client protocol. It cannot lower or replace captured eager speeds and
authorizes no production, deployment, or LocalMaxxing claim.

## Frozen packet

- graph base launcher SHA-256:
  `533be64e1c7584448c07a5f8895301a32288f4b0472948a91d87235e78c6f09f`
- wrapper `tools/launch-tp4-mtp0-current-piecewise-graph-a3.sh`:
  `d3ca914ddfb494ee55e75dca6342d83357b402f60bb028d523ea6df16b37b915`
- client adapter `tools/run-tp4-mtp0-current-piecewise-graph-a3-client.sh`:
  `901ff0f33d43588a0b746af25ecf32feb396709c94ea9282b32a140975cb5f31`
- mechanically derived client SHA-256:
  `2fde4a7875168c0df0e217dc454190654ba70c81184d0f7d3f169561fd0bd9ef`
- watchdog `tools/watch-tp4-mtp0-current-piecewise-graph-a3-resources.sh`:
  `6e721c58c0cd0c0e00b25c9ae5c0bdb71fbd362de45050696e74603f248e0651`
- outer supervisor
  `tools/supervise-tp4-mtp0-current-piecewise-graph-a3-swap64.sh`:
  `5e318162789b56bcb83d43e6212c58c336850bea46958eee8727acbd18e1ae32`
- mechanically derived descendant supervisor SHA-256:
  `7e2d20bc20294da07c524f7e60196c4b0ef3b555d9aa79572e2c9cd7a46544ca`

Frozen administrative identity:

- attempt `3`, port `19677`;
- state `/tmp/q38-mtp0-current-piecewise-graph-a3` and outer state suffix
  `-a3-swap64`;
- run/cache/compile/RPC and ordinary supervisor paths use fresh suffix
  `qwen38-flash-next-fp8-tp4-ep4-piecewise-mtp0-4352-r1-attempt3`;
- resource evidence uses the same suffix plus `-resource`;
- swapfile `/var/tmp/q38-piecewise-graph-a3-64g.swap`, exact logical size
  68,719,476,736 bytes and expected active size 67,108,860 KiB;
- `swapon -p -1` and an exact active-row priority gate of `-1`.

## Unchanged protocol and safety

The current model revision remains
`bcd9f01ddc9cff2316eb84281bebcd5b058bddce`, vLLM remains
`1372c62d975c554f4b465c8299bc5f3295301ceb`, XPU kernels remain
`ad25aa9f69a2171612b9c6b83dfa82c69559f9e4`, and staged build remains
`2f829747503c77d4814834dffd0840fb1dd9f75a`. The cell remains TP4/EP4,
eager-off PIECEWISE graph, MTP0, max length 4,352, 201,326,592 cache bytes,
capture size one, and the accepted selective UVA placement.

Before model work, the supervisor still requires a fresh root-ext4 swap path,
64 GiB plus the retained 40-GiB root floor, exact full allocation and stable
device/inode/ownership/mode, unchanged pre-existing swap layout, and the exact
accepted active row. The watchdog and outer latches retain all attempt-2
memory, swap, root, PSI, OOM/RxErr, heartbeat, and inner-exit stops. Safe
teardown still requires descendants stopped, at least temporary-swap-use plus
16 GiB `MemAvailable`, bounded `swapoff`, stable identity/allocation, exact
`unlink`, and restoration of the original swap layout; otherwise the active
file is preserved and the result fails.

Only after health may the same recovery, frozen semantic parity, alternating
96/96 plus 96/96 exact graph replay, runtime PIECEWISE evidence, and three
p146/o256/c1 short rows run. Every measured row still rejects nonzero
`pswpin`/`pswpout` deltas or increased temporary-swap use before it can write a
PASS/stop sentinel. Partial and negative evidence is retained, while all prior
speeds remain protected.

## Prepared commands

These commands have not been run:

```bash
/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/tools/supervise-tp4-mtp0-current-piecewise-graph-a3-swap64.sh
/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/tools/run-tp4-mtp0-current-piecewise-graph-a3-client.sh
```

Do not launch until a separate read-only audit confirms the current hashes,
mechanical-diff contract, fresh paths, and live admission state.
