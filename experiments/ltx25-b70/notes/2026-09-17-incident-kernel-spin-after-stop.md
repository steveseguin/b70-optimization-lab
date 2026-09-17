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
