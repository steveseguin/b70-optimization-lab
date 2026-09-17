# Incident 2026-09-17 ~06:58 UTC: processes spinning in the kernel after a clean server stop

Sequence (UTC): 06:49 packet 73 server up; 06:51 the two-clip arm's driver
stopped on a labeling defect (six prompts completed, clips exact so far);
06:53:13 one SIGINT, server exited in 8 s, render nodes free; 06:53–06:58
offline edits; 06:58 the CPU test `test-ltx-pipeline-lookahead.py` (imports
torch, no GPU work) never returned. By 07:09: load average 28→31, two python
processes in state R, single-threaded, immune to SIGKILL and to
faulthandler; `ps`, `journalctl` and `sudo dmesg` block (`ps` waits in
`__access_remote_vm`, i.e. on those processes' memory-map lock);
`systemd`, `systemd-journald`, `smartd`, `snap` and a `kblockd` worker in
D state; NVMe idle (nothing in flight). Runtime PM of all four B70s was
pinned on and stayed on. The kernel is looping in a driver path with a lock
held: the same silent-lockup class as before, this time observed while it
formed, ~5 minutes after a clean xe process teardown, triggered by a
process that merely initialised torch.

Conclusion so far: the runtime-PM race was real and is fixed, but it was
not the only cause. Teardown of an xe process followed by a new device
initialisation within minutes remains a lockup trigger on this kernel and
driver (7.0.0-31-generic, xe with GuC 70.72.1, Level Zero UR V2). Until the
driver/kernel side is addressed, the only mitigations under the lane's
control are: never stop the sealed server (one process for the whole
session, every arm on it), and never start a second torch process while it
is running or within minutes of its exit.

## Update 14:05 UTC: the freezes are independent of the workload; the stack changed a week before they began

Boots on 2026-09-17 (EDT): 08:56→09:09 froze with the LTX server idle after
a finished campaign; **09:33→09:50 froze with nothing running at all** (no
session, no server, no probe). With yesterday's 23:40 and 23:48 idle-boot
lockups, four freezes have now happened with no GPU work in flight and all
four cards pinned on. No kernel line precedes any of them.

What changed before the freezes began: `linux-firmware` upgraded on
2026-09-03 and brought xe GuC firmware **70.72.1** (May notes record 70.49.4;
a backup of the Ubuntu 70.44.1 file was taken on 09-02 into
`/lib/firmware/xe/backup-ubuntu-70.44.1/`), and the kernel moved to
**7.0.0-31-generic** on 2026-09-05 (7.0.0-30 is still installed). The
documented lockups begin on 09-05 (Qwen lane) and 09-14 (this lane).

Reversible things to try, in order (each needs a reboot, so the user's
call): boot 7.0.0-30 from GRUB; restore the 70.44.1 GuC firmware from the
backup directory and rebuild the initramfs; enable kdump with
`kernel.hardlockup_panic=1` so the next lockup leaves a crash dump instead
of nothing. Until one of these is tried, GPU work on this host will keep
being interrupted regardless of how carefully it is run.
