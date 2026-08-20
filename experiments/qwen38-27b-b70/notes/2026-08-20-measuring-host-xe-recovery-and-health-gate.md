# Measuring-host xe recovery and health gate

Date: 2026-08-20

Host: `steve-b70s` / `10.0.0.65`

Hardware: four Intel Arc Pro B70 GPUs; about 125 GiB system RAM

## Trigger and passive classification

The journal showed repeated GuC reset/reject events on the B70s at PCI BDFs
`23:00.0` and `27:00.0`, including events while no workload owned the render
nodes. No vLLM, llama.cpp, benchmark, or model-server process was live. Before
recovery, the host was checked for render-node holders, display ownership,
`xe.disable_display=1`, and AST console use. The display manager was inactive.

The user explicitly authorized GPU recovery. PCI FLR was not used because it is
a known unsafe path on this stack, and the host was not rebooted.

## Recovery

All live xe-bound B70 BDFs were resolved dynamically, then all four devices
were unbound before reloading the driver:

```bash
for bdf in 0000:23:00.0 0000:27:00.0 0000:43:00.0 0000:47:00.0; do
  echo "$bdf" | sudo tee /sys/bus/pci/drivers/xe/unbind >/dev/null
done
sudo modprobe -r xe
sudo modprobe xe
```

The local sudo credential file was used through stdin and was never printed or
copied into the repository.

## Required post-reload gates

All gates passed:

- `xpu-smi discovery` returned exactly four B70s with the expected BDF/UUID
  mapping;
- idle memory was about 42.9 MiB on each device;
- a device-local compute smoke passed on every card;
- the four-device peer-read binary reported `peer kernel read ok across 4
  devices`;
- `scripts/check-qwen36-xpu-xccl-health.sh` passed all four per-card compute
  smokes and a four-rank XCCL allreduce;
- a known-good Qwen3.6 Q8/VDR2 exact-generation canary passed its output gate,
  teardown gate, and pre/post idle-memory check;
- the post-reload journal window contained no new xe/GuC reject events.

The successful canary is retained outside Git at:

```text
/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/recovery/post-xe-reload-vdr2-canary-20260820
```

Its `completion-status.json` is `PASS`, and the run contains its own artifact
checksum manifest. An earlier attempt at
`post-xe-reload-q36-q8-smoke-20260820` failed before server launch because its
expected `/dev/shm` runtime was absent; it is preserved as an infrastructure
failure and is not evidence of a GPU failure.

## Outcome and next gate

The measuring host is healthy for fresh work. Recovery does not validate any
previously aborted arm. Every new Qwen3.8 launch must use the fail-closed
direct-and-ordinary model verification gate added at `c8db35513`, because the
same host previously returned disk-correct bytes through direct I/O but
corrupted bytes through ordinary page-cache reads.
