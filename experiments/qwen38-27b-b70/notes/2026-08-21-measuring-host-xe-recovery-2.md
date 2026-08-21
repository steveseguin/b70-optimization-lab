# Measuring-host xe recovery 2 and health gate

Date: 2026-08-21

Host: `steve-b70s` (four Intel Arc Pro B70, about 125 GiB RAM)

## Trigger and passive classification

GPU3 (`0000:47:00.0`) failed its preregistered stock-control health diagnostic
at 02:47 with a kernel Xe/GuC timeout-and-reset storm
([terminal result](2026-08-21-qwen38-gpu3-incumbent-control-health-result.md)).
The storm quiesced, but at 09:55 a single passive `xpu-smi discovery` query
re-lit it: 562 kernel events in under three minutes, every one on
`0000:47:00.0`, each `Timedout job ... in no process [-1]` with no process
holding any render node — the documented poisoned-wedge signature. The
pre-reload evidence window is preserved in the session scratchpad and the
kernel journal. No model, benchmark, or server process was live.

The user explicitly authorized this host-wide recovery attempt through an
interactive confirmation. PCI FLR was not used and the host was not rebooted.

## Pre-checks and recovery

Pre-checks passed: no render-node holders (`fuser` empty on all four render
nodes), display manager inactive, console on the `ast` adapter, and
`xe.disable_display=1` present on the booted kernel command line.

All four live xe-bound BDFs were resolved dynamically and unbound, then the
module was reloaded:

```bash
for bdf in $(ls /sys/bus/pci/drivers/xe/ | grep '^0000:'); do
  echo "$bdf" | sudo tee /sys/bus/pci/drivers/xe/unbind >/dev/null
done
sudo modprobe -r xe
sudo modprobe xe
```

For the record: a first scripted attempt was a verified no-op — a stdin
redirect for the sudo credential clobbered the pipe feeding `tee`, so no BDF
was written, all four devices stayed bound, and `modprobe -r` correctly
refused on the live refcount. The corrected sequence validated the sudo
timestamp first and verified each unbind individually (`remaining bound: 0`)
before touching the module. The sudo credential was fed through stdin only
and never printed.

All four devices re-probed immediately after reload.

## Required post-reload gates

All gates passed:

- `xpu-smi discovery` returned exactly four B70s at `23/27/43/47:00.0` with
  the expected BDF-embedded UUID mapping;
- idle VRAM on each device (GPU3 free `34197340160` of `34242297856` bytes);
- single-device compute smoke passed on every card and the four-rank XCCL
  barrier/allreduce passed (`scripts/check-qwen36-xpu-xccl-health.sh`,
  exit 0);
- the four-device peer-read binary reported
  `peer kernel read ok across 4 devices`;
- the known-good Qwen3.6 Q8/VDR2 exact-generation canary passed as
  `official-isolated` with every exact-result check true
  (`status: PASS`, `post_512_canary_passed: true`), retained outside Git at:

  ```text
  /mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/qwen36-27b-q8_0-f16kv-promotion512-gpu0-short-official-isolated-prefill-ub1024-ub1024-q8-vdr2-candidate-vdr2-20260821T142153.840113911Z
  ```

- the post-reload kernel journal window from 10:15 through the complete
  canary workload contains zero Timedout/Engine-reset/GuC-error/reject
  events (the only xe line is the deletion of the stale pre-reload
  coredump).

## Outcome and next gate

The measuring host is healthy for fresh work. Recovery does not validate any
previously aborted arm, and it does not by itself clear GPU3 for the Q64K32
lane: per the [GPU3 health terminal result](2026-08-21-qwen38-gpu3-incumbent-control-health-result.md),
the next defensible step there is a **newly preregistered fresh-root
incumbent-control health test** on GPU3. Only after that passes may a
candidate or two-GPU operator campaign be considered. New Qwen3.8 launches
must continue to use the fail-closed direct-and-ordinary model verification
gate.
