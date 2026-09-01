# Qwen3.8 Flash-Next FP8 M1 W13-N32 XPU-graph confirmation A2

Date: 2026-09-01
Status: frozen; GPU execution blocked pending root-NVMe link clearance

## Successor scope

A1 is preserved unchanged as a pre-device infrastructure negative. It stopped
after one corrected local-NVMe endpoint event during its impossible
continuously-zero idle admission, before multi-GiB checkpoint-shard hashing or
device work.
A2 removes only that 60-second zero-change admission and reduces the
confirmation from three seeds to the discovery seed `20260827`. The dynamic
total event cap and every other host, identity, correctness, timing, teardown,
and evidence guard remain.

The A1 result is recorded in:

- `notes/2026-09-01-moe-m1-w13-xpu-graph-confirmation-a1-idle-admission-negative.md`;
- `data/20260901-moe-m1-w13-xpu-graph-confirmation-a1-idle-admission-negative.json`.

## Frozen source and model identity

A2 derives its full runner byte-for-byte from the immutable A1 runner and
refuses source drift:

- A1 base runner SHA-256:
  `c81a2240542b75a3bf932fccf606f2db4b2872d201171c76f8e6f48ac5a7fad3`;
- A2 wrapper SHA-256:
  `65d997316bd040dae797f772dd5e14973c72504d9ea9e20e8568f4d37a646f4b`;
- derived A2 runner SHA-256:
  `6c9e672737d46c651c3909ecd7d57693308d121f87a2b93d6bacee3e5a87249a`;
- A2 summarizer SHA-256:
  `e61b13c08c6738d9e552c10a0f751ffe726216518dd419bc3b08b73667137113`;
- A2 summarizer tests SHA-256:
  `7ff59ed2b281ddea3841adf789bed4e7abdaa817444843e8f3ea1cb541056077`;
- root-NVMe clearance validator SHA-256:
  `9e23b7bab722c502e58181e913382ad0035f0c5cd835ec0560bd1eedc81b9adc`;
- clearance-validator tests SHA-256:
  `28eb287e689f8500453b467dbe68883ed4fc96344c8babce5256532670b9506f`;
- shared component gate SHA-256:
  `8828a3b42766a96f014299967af94cbde48410abd92d64183685dbf737ce05a1`;
- shared gate tests SHA-256:
  `ee321600d904ea34603d4d4a72c59fd77e9ced6dd7cbd025af958031a0b09603`.

All A1 model and runtime bindings remain exact: external
`/dev/sda2 fuseblk /mnt/usb-models` checkpoint only, model revision
`bcd9f01ddc9cff2316eb84281bebcd5b058bddce`, vLLM head
`cbc3cb588a7cae8dcc489fb4dfc1a800d19980d9`, kernel head
`e421889999bc1e5a5f11044d14548b9afdba644d`, exact staged-runtime manifest
and source hashes, and no tracked source drift.

The same four exact layer-0/layer-47 shards are hashed once before device work.
The receipt remains bound to SHA-256, path, size, device, inode, and nanosecond
mtime/ctime; each fresh process verifies it. Writable Triton, vLLM,
TorchInductor, XDG, Torch-extensions, and temporary paths remain isolated
under the unused A2 root
`/dev/shm/q38-w13-m1-xpu-graph-confirmation-a2`, which the finalizer removes.

## Frozen 8-cell matrix

The sole candidate remains nested W1
`{"W1_CONFIG":{"BLOCK_SIZE_N":32}}`; W2 is unchanged.

- layers: `0`, `47`;
- logical EP ranks: `0`, `1`, `2`, `3`;
- seed: `20260827` only;
- cells: `8`;
- fresh processes: `24`.

Every cell runs control-before, candidate, control-after in strict sequence.
Candidate and control-after bind to that cell's raw one-line control-before
authority. The first layer-0/rank-0 control is the required one-XPU smoke.
Every process retains 100 changing inputs with exact eager/graph and authority
hashes. A candidate failure runs only its matched control-after, then stops the
confirmation failed closed.

## Acceptance

A2 passes only if:

- all eight cells and all 24 process exits are exact;
- every control bracket drifts at most `2%`;
- median within-cell matched reduction is at least `3%`;
- at least seven of eight cells have a strictly positive reduction;
- no cell regresses by more than `2%`.

Only matched within-cell ratios are aggregated. Raw latency is never pooled
across ranks or layers.

## Retained host and evidence gates

A2 establishes all baselines dynamically immediately before preflight and
keeps:

- total local-NVMe corrected-event delta at most `16`;
- root-port corrected-event delta exactly `0`;
- local-NVMe read delta at most 4,194,304 sectors (2 GiB);
- swap used exactly zero;
- `MemAvailable` at least 96,000,000 KiB;
- memory-full PSI `avg10` at most `0.10`;
- no fatal/recoverable/uncorrected, DPC, link-down, controller-down, or severe
  B70 event;
- per-arm timeout 420 seconds and total deadline 5,400 seconds;
- sequential execution, owned-process/cache teardown, canonical health receipt,
  and verified final `SHA256SUMS`.

The continuously-zero 60-second idle rule is absent. Crossing any retained
limit stops the active process group before another cell starts. Final
`xpu-smi` remains diagnostic best-effort; it cannot authorize success.

## Mandatory maintenance clearance

The hardware audit prohibits another GPU attempt until SSD/link maintenance
has been completed and independently qualified. A2 source-only and
validate-only modes remain available for static review. Actual execution now
stops before derived-runner creation or any device work unless this exact,
non-symlink file exists on the frozen external evidence filesystem:

`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/host/20260901-root-nvme-link-clearance-v1.json`

The file uses a closed schema: every shown key is mandatory and extra keys are
rejected.

```json
{
  "schema_version": 1,
  "status": "pass",
  "classification": "q38_root_nvme_link_clearance_v1",
  "firmware_after": "5B2QGXA7",
  "idle": {
    "seconds": 1800,
    "local_nvme_corrected_delta": 0,
    "root_port_corrected_delta": 0
  },
  "bounded_read": {
    "local_nvme_corrected_delta": 0,
    "root_port_corrected_delta": 0
  },
  "smart": {
    "critical_warning": 0,
    "media_errors": 0
  },
  "b70_devices": [
    {"device_id": 0, "device_name": "Intel(R) Arc(TM) Pro B70 Graphics", "pci_bdf_address": "0000:23:00.0"},
    {"device_id": 1, "device_name": "Intel(R) Arc(TM) Pro B70 Graphics", "pci_bdf_address": "0000:27:00.0"},
    {"device_id": 2, "device_name": "Intel(R) Arc(TM) Pro B70 Graphics", "pci_bdf_address": "0000:43:00.0"},
    {"device_id": 3, "device_name": "Intel(R) Arc(TM) Pro B70 Graphics", "pci_bdf_address": "0000:47:00.0"}
  ]
}
```

`idle.seconds` may exceed `1800`; all other values and the four-device order
are exact. Boolean values are rejected where integers are required. The
firmware-after value must be `5B2QGXA7`; both the at-least-30-minute idle and
the bounded-read windows must have zero local-NVMe and root-port corrected
deltas; SMART critical warning and media errors must both be zero. A missing,
malformed, stale-firmware, dirty-link, dirty-SMART, or wrong-topology receipt
cannot create the derived runner and cannot reach an XPU process.

New paths are unused before launch:

- evidence:
  `/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/components/20260901-moe-m1-w13-xpu-graph-confirmation-a2`;
- cache: `/dev/shm/q38-w13-m1-xpu-graph-confirmation-a2`;
- derived runner:
  `/dev/shm/q38-w13-m1-xpu-graph-confirmation-a2-derived.sh`;
- lock: `/tmp/q38-w13-m1-xpu-graph-confirmation-a2.lock`.

No reboot or full-model load is part of A2.
