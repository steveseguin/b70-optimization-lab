# Qwen3.8 Flash-Next FP8 M1 W13-N32 XPU-graph confirmation A1

Date: 2026-09-01
Status: frozen before GPU execution

## Trigger and question

The bounded W13 discovery completed all six matched C/A/C brackets. Its sole
winner was nested W1 `BLOCK_SIZE_N=32`: all 100 changing eager and graph
outputs were exact, candidate latency was `166.674820 us` versus controls at
`215.274540 / 215.561060 us`, control drift was `0.133007%`, and the matched
reduction was `22.627183%`.

Discovery summary SHA-256:
`5b3113cb35de8ccc3efd1404ed47bfbc26520001cc3c3b0164d968bf6e81f20f`.
Emitted confirmation-packet SHA-256:
`a4a9acf63c4b75d08efb06dd66b24d95c1e5c21a807fb9b498ba537de8385b06`.

This confirmation asks whether that exact W13-only win generalizes across the
two boundary layers, all four logical EP ranks, and three fixed input seeds.
It remains a one-B70 component result. It does not alter a serving result or
authorize an endpoint claim.

## Frozen checkpoint and runtime identity

- external checkpoint only:
  `/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8` on exact mount
  `/dev/sda2 fuseblk /mnt/usb-models`;
- model revision: `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`;
- index SHA-256:
  `0419e2c2dfbb925257d7409405433a793cf7ff7d96f3eba882a815ec6d9fe7a6`;
- config SHA-256:
  `99c11efba4012d0f760f4e4831a8d6cafd845044e21d0aa9e6d9e70a15a90a8d`;
- vLLM head: `cbc3cb588a7cae8dcc489fb4dfc1a800d19980d9`, clean tracked
  source required;
- vLLM XPU kernels head:
  `e421889999bc1e5a5f11044d14548b9afdba644d`, clean tracked source
  required;
- staged runtime:
  `/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70`, manifest
  SHA-256
  `9fa443fdb7a6d0042cf04f859cc6fd6a7bdc09943e16cafb4ea084573c892d2b`;
- fused-MoE source SHA-256:
  `4b376eb5e22e7972a1d70e4012999650ab961719d6309cbec27a6104fa64d0a0`;
- Triton-experts source SHA-256:
  `b8a461b712b88cf6ab5ba4f49029fddce3a501f7ff909b276b6de04b808da4c2`;
- modular-kernel source SHA-256:
  `1e60aca6ed0dd4fcb46d577897ff1651f27a6130b3449d22265c0c791beec5d5`.

The four distinct real-weight shards are frozen and hashed once before device
work:

| Layer | Shard | Bytes | SHA-256 |
|---|---|---:|---|
| 0 | `model-00002-of-00131.safetensors` | 1,678,209,208 | `6841fe21fa8a8a7a693c585efe65cd2732889095b696da88bda0cb287366910b` |
| 0 | `model-00003-of-00131.safetensors` | 993,901,136 | `974a2a2ab551f8f1405a4955ab32a8721c68c73dd85b382491d9f0e6a34ee752` |
| 47 | `model-00119-of-00131.safetensors` | 1,678,211,256 | `36008b48c4480085bfd1a81439d70d1029cfaf06cfdd037cec19b491a40659ec` |
| 47 | `model-00120-of-00131.safetensors` | 1,109,903,856 | `49e4f90d92f60f6489bfe6d3e5250d8fe879c5995ae72ce67379cc7187fa4b0a` |

The runner then creates a deterministic checksum receipt with SHA-256
`4299f69d6231afaf0874de85f15bfa6ffc3c5fb97a4853f04ddffb5504d57dbc`.
Every fresh process verifies that receipt digest and its selected shards' exact
path, size, recorded digest, filesystem device/inode, and nanosecond mtime and
ctime. A same-size shard rewrite after the one-time hash therefore fails the
frozen stat identity before device work. This avoids hashing the same
multi-GiB files 72 times. Omitting the new paired receipt arguments keeps the
component gate's original per-process hashing behavior.

Frozen experiment files:

- component gate SHA-256:
  `8828a3b42766a96f014299967af94cbde48410abd92d64183685dbf737ce05a1`;
- component-gate tests SHA-256:
  `ee321600d904ea34603d4d4a72c59fd77e9ced6dd7cbd025af958031a0b09603`;
- confirmation runner SHA-256:
  `c81a2240542b75a3bf932fccf606f2db4b2872d201171c76f8e6f48ac5a7fad3`;
- confirmation summarizer SHA-256:
  `fd403e8f5435612b9f1216598947ee156cdf2f2f4de5a72de5bfea5dbd8355e0`;
- summarizer tests SHA-256:
  `8bd984e453d205869100a8651829e44acee26e1791738d2c2e075edff6479e92`.

## Frozen matrix and component contract

The exact candidate is `{"W1_CONFIG":{"BLOCK_SIZE_N":32}}`; W2 remains the
protected M16/N64/K128/group-1/split-K-1/stage-4/warps-8 configuration.

The 24 cells are:

- layers `0` and `47`;
- logical EP ranks `0`, `1`, `2`, and `3`;
- seeds `20260826`, `20260827`, and `20260830`.

Each cell owns three fresh processes in order: control-before, candidate, and
control-after. Candidate and control-after consume that cell's raw one-line
control-before result through `--control-authority-json`. The first
layer-0/rank-0/seed-20260826 control is the actual one-XPU smoke and must pass
or stop. A candidate failure is followed only by its matched control-after,
then the whole confirmation stops failed closed.

Every arm uses the production M1 EP4 shape, exact selected checkpoint experts,
100 changing inputs, exact eager/graph hash-list equality, a clean static XPU
graph, five capture warmups, ten timing warmups, and 15 batches of 200 replays.
Capture, compilation, input copies, and shard loading are outside timing.

## Frozen interpretation

Confirmation passes only if:

- all 24 cells and all 72 process exits are exact;
- each cell's control-before/control-after drift is at most `2%`;
- the median of the 24 within-cell matched reductions is at least `3%`;
- at least 20 cells have a strictly positive matched reduction;
- no cell regresses by more than `2%`.

Only within-cell candidate/control ratios are aggregated. Raw latency from
different ranks, layers, or seeds is never pooled. Any failed gate preserves
the discovery result but does not promote N32.

## Frozen host-safety boundary

The external-checkpoint discovery still coincided with a local-NVMe corrected
counter increase of 14, although the host stayed healthy. Confirmation
therefore establishes the current counters and local-root read counter
dynamically at its own start. A 60-second idle preflight must then have exactly
zero corrected-count change. The baseline precedes hashing the four shards, so
all checksum, preflight, and device work is included in these fail-closed
limits:

- local-NVMe corrected-event delta at most `16` from that dynamic baseline;
- root-port corrected-event delta exactly `0`;
- local-NVMe reads at most 4,194,304 sectors (2 GiB) from the dynamic baseline;
- zero swap use, `MemAvailable` of at least 96,000,000 KiB, and memory-full
  PSI `avg10` no greater than `0.10`;
- no fatal/recoverable/uncorrected, DPC, link-down, controller-down, or severe
  B70 device event;
- a hard total deadline of 10,800 seconds.

Health is sampled during every arm and between every cell. Crossing a limit
terminates the owned process group and prevents another cell from starting.
All writable Triton, vLLM, TorchInductor, XDG, Torch-extensions, and temporary
paths are isolated below the otherwise-unused
`/dev/shm/q38-w13-m1-xpu-graph-confirmation-a1`; source, staged runtime, and
the venv remain in place, and no bulk mirror is made. The cache root is removed
by the exit trap.
The exit trap stops the active process and journal follower, captures the full
kernel window and final counters, and writes and parses `health-receipt.json`.
Receipt creation and the final verified `SHA256SUMS` are mandatory for a zero
exit. If either late finalization step changes the exit code, the initially
encoded receipt is preserved under an explicitly invalid name and a
`failed_closed` receipt with the final nonzero code is written, re-parsed, and
re-hashed. Thus a canonical `pass` receipt cannot contradict a nonzero final
exit. Final `xpu-smi` discovery is diagnostic best-effort and is explicitly
not a success gate because counter, journal, process, cache, and component
exits already own the frozen safety decision. The evidence root is never
reused:

`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/components/20260901-moe-m1-w13-xpu-graph-confirmation-a1`

No reboot and no full-model load are part of this packet.
