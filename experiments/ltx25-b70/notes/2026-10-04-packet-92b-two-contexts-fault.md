# Packet 92b: a second process context on xpu:3 ended in a GPU fault within 90 seconds (2026-10-04)

Server `encoder-server-decodeproc-92b` (packet
`prepared-encoder-decodeproc-92b`, manifest `988884d3...`, kernel 7.0.0-38,
GuC 70.44.1, `LTX_BUSY_WINDOWS=0 LTX_DECODE_CHILD=1`), launched 02:40:05 UTC.
The decode child process (pid 184500) held its own Level Zero context and
VAE copies on xpu:3 next to the server's text shard and VAEs.
[Build note](2026-10-03-packet-92b-build.md).

## What happened

| Time (UTC) | Event |
| --- | --- |
| 02:43:42 | warm arm done |
| 02:44:13-02:44:41 | child probe: **exact**, 10/10 fixtures byte-identical from the child process |
| 02:45:11 | control arm starts (decode in the server; the child idle but resident) |
| 02:45:27, 02:46:11 | `hard LOCKUP on cpu 21`, `g2h_read`, twice in 44 s (card 0000:43:00.0) |
| 02:46:41 | card 0000:47:00.0 (xpu:3): `Fault response: Unsuccessful -ENOENT`, `Engine memory CAT error [18]: class=ccs`, engine reset, `Timedout job ... in python [184372]` (the server), device coredump |
| 02:46:42 | prompt `f92b-ctl-14` fails (`Decode-ahead for clip 210200 failed`); FAULT latched; runner exits rc 2 and leaves the server up |

The child arm never ran. Fourteen control prompts completed before the fault.

Stopping: one SIGINT stopped ComfyUI and the child exited, but four worker
threads stayed at 100 % CPU waiting on events of the reset engine and the
process never finished. It was terminated with SIGTERM as a single incident
action; that produced two further `bcs` engine resets (0000:47 and 0000:23).
The host stayed up (`hardlockup_panic=0`).

Evidence: kernel lines and the xe device coredump in
`data/2026-10-03-xe-guc-hard-lockup/` (repo root `data/`).

## Reading

1. A separate process can decode byte-exactly (the probe), so the transport
   and the child are sound.
2. Two contexts on one card are not safe on this driver stack: within 90 s of
   mixed use the server's context on xpu:3 took an unrecoverable page fault.
   Whether the cause is VRAM pressure across contexts, the interrupt lockups
   that preceded it by seconds, or the driver's handling of two fault-mode
   VMs is not established.
3. The lockup rate was higher than in single-process runs (two in 44 s
   against two in about 15 minutes).
4. With the pipeline shown to be GPU-bound
   ([budget note](2026-10-04-gpu-budget-from-driver-counters.md)), the
   process split had little to offer anyway. **The process-split line is
   closed**; packets 93-95 of the design note are not to be built.

The boot is burned for GPU work: the sealed launcher refuses launches once
the kernel journal carries a fault line. GPU runs resume after a reboot.
