# Single-card slab probe result (2026-10-09 01:39 UTC): indirect gather is correct; the fault is a teardown-time blitter fault

Boot 4aafe57b (fresh after the owner's reboot; zero fault lines before the probe). Card 0000:23:00.0 only
(`/dev/dri/renderD130` mapped as renderD128 in the container), image `vllm/vllm-openai-xpu@sha256:e4446310…`
(torch 2.13.0+xpu, triton 3.7.2+xpu, vllm 0.30.0+xpu, vllm-xpu-kernels 0.1.14.1), exact-size pinned allocator
aliases, `NEOReadDebugKeys=1 EnableDeferBacking=0`, no model, no distributed group. Receipts:
`reopen-20261008/runs/probe-indirect-20261009/` (receipt.json, Triton IR, kernel-latest.log, watcher.json/STOP).
Two earlier directories record attempts that never reached the device (docker `--device` colon parsing; the
package mounted at the wrong depth for `screen.py`'s `HERE.parents[2]`); the printer was fixed for both.

## What the probe showed

- `bytes_equal: true`: one Triton gather launch (4 programs × 4096 B) through the production signed-offset table
  (`resident_base + delta`, host UVA addresses 0x7911… reconstructed on the CPU) read the pinned host slab's
  interior view correctly; output SHA-256 equals the expected rows `[3,0,2,1]`. The table-only indirect
  contract that attempt 7's analysis suspected **works** on this runtime for a pinned host slab.
- `usm_query.status: unavailable` (no read-only pointer-kind query in the launch queue's context in this build).
- The watcher's read right after the readback (01:39:26.9 UTC) saw no new fault lines (`passed: true`).
- **01:39:27.87 UTC**, with the probe idle in `bytes_equal_waiting_postflight` (~1 s after the output was back on
  the CPU, before process exit at 01:39:28): kernel `xe 0000:23:00.0 … Faulted Address 0x0000d556a74c0000,
  FaultType 0, FaultLevel 4, Fault response: Unsuccessful -ENOENT`, then `Engine reset: engine_class=bcs,
  logical_mask 0x1, guc_id=6`. One card, one fault, one blitter reset; no CAT error, no coredump line. The
  faulted address is neither a device buffer (those sit at 0xFFFFFFFFFF6…) nor a host UVA address (0x7911…).
- Health probe afterwards: all four cards pass (`postflight-after-probe-fault-20261009T0140Z.json`). First
  incident of this boot.

## Reading

The compute path is not the defect. A copy-engine job touched an unmapped GPU virtual address after the work
had finished: a trailing blitter operation (readback staging, allocator event/free, module unload) racing a
free, inside the container's user-mode driver. Attempt 7's four-card fault (ccs CAT errors on the first forward)
and the 14:04 UTC OOM-teardown fault are also inside this image's runtime, while the LTX lane (host venv
`ltx25-baseline`) ran the same cards all day and tonight without a fault line. The common factor to test next
is the image's compute runtime (NEO / IGC / Level Zero loader versions) against the host's kernel 7.0.0-39 xe
driver, not the MoE addressing. The direct-host-pointer variant was **not** run: it cannot discriminate anything
once the indirect gather is byte-correct, and a second incident on this boot would halt the LTX lane too.

## Next (CPU first)

1. Codex: compare NEO/IGC/L0 versions inside the image vs the host's packages and the LTX venv's runtime (no
   `--device`); check NEO release notes for bcs/-ENOENT teardown faults; propose either bind-mounting the host
   UMD into the container or an image whose runtime matches the host's; re-read the attempt-7 window for
   free/teardown events preceding the first CAT error.
2. Only then a second tiny probe on one idle card with the chosen runtime, same stop rule.
