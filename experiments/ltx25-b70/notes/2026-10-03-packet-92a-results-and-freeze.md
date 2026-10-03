# Packet 92a: interpreter-lock contention refuted by two arms; host froze seconds into the 20 ms arm (2026-10-03)

Server `encoder-server-gil-92a` (packet `prepared-encoder-gil-92a`, manifest
`b201580c08ea6e540a4b2bee70b1fd4a4e8480c254c37391e5be07773d329fb9`,
`LTX_BUSY_WINDOWS=0`), launched 21:52:09 UTC on boot 6ddb73fa (kernel
7.0.0-34, GuC 70.44.1, memory blocks 53-57 offline, `hardlockup_panic=1`).
Runner `scripts/run-campaign-92a.sh`. Receipts in `data/gil-92a/`.
[Build note](2026-10-03-packet-92a-build.md), [design](2026-10-03-process-split-design.md).

## What ran

| Arm | Switch interval | Clips exact | Interval median / mean | Sampler job | Encode job | Decode job | Lane CPU-s per wall-s | Busiest thread | Lock-wait median / p95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| idle baseline | 5 ms | - | - | - | - | - | - | - | 0.064 / 0.064 ms |
| s05a | 5 ms | 37/37 | 1.337 / 1.668 s | 2.553 s | 2.961 s | 1.313 s | 3.776 | 0.834 | 0.064 / 0.609 ms |
| s01 | 1 ms | 37/37 | 1.404 / 1.634 s | 2.539 s | 3.132 s | 1.408 s | 3.929 | 0.890 | 0.064 / 0.609 ms |
| s20 | 20 ms | not run | | | | | | | |
| s05b | 5 ms | not run | | | | | | | |

(`scripts/analyze-gil-92a.py <run> data/gil-92a`; its verdict line is
INDETERMINATE only because two arms are missing.)

## Reading

1. **The interpreter lock is not the bottleneck.** The probe thread gets the
   interpreter back in 0.064 ms at the median under full load, the same as on
   an idle server, and a fivefold change in the switch interval moved the
   sampler job by 0.5 %. Both are on the "refute" side of the design note's
   thresholds (lock wait under 0.3 ms, arms within 3 %).
2. **The lane's threads burn 3.8-3.9 CPU cores, with the busiest thread at
   0.83-0.89 of a core.** That time is outside the interpreter lock, in
   native code: the SYCL/Level Zero runtime and driver submission path, or
   spinning inside them. The "CPU at most 0.6" refute rule does not hold, so
   the picture is: each worker thread is close to CPU-bound in native code.
3. Together with packet 91b (adding one worker slowed every other stage,
   independent of card) the open question becomes what the threads share
   below Python: a process-wide lock in the GPU runtime, the memory bus, or
   CPU frequency. A sampling profile of the live server answers where the
   CPU time goes; `scripts/run-campaign-92p.sh` (one 160-prompt arm at the
   default interval, same packet, run name `encoder-server-gil-92p`) exists
   to hold the server busy for that.
4. One process per stage may still help if the shared thing is a per-process
   runtime lock, but the reason is no longer the one in the design note, and
   it must be shown before it is built.

## The freeze

- 22:01:52 UTC: arm s01 finished and was committed. 30 s settle.
- about 22:02:22: knob to 20 ms applied; arm s20 started.
- 22:02:28.6 UTC: last file written (`pipeline-done-sample-209389.json`,
  zero length). The host was frozen and was reset by hand; it came back at
  22:44 UTC on kernel 7.0.0-38 with reason `system reset pin`.
- Kernel log: nothing. A user-level follower of the kernel journal, syncing
  every line to disk, has no kernel line after 22:00:46 UTC, and the previous
  boot's journal has no lockup, fault or reset line.
- 15 zero-length receipts in the run dir (prompt s20-01).

Cause not established. The known-bad memory was fenced. `hardlockup_panic=1`
with `panic=0` was still set, so a GPU interrupt lockup of the kind recorded
in September would halt silently, exactly like this. The freeze came within
seconds of the first GPU work under a 20 ms switch interval, after three
complete campaigns and two arms at 5 ms and 1 ms without incident; that
setting is not to be used again on this host without a reason.

After the reboot: memory blocks 53-56 offlined again (57, a margin block with
no observed errors, could not be offlined on this boot and stays online);
`hardlockup_panic` and `softlockup_panic` set to 0 for the boot.
