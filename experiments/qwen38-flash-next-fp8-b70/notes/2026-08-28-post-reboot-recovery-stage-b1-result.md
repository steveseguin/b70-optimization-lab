# Flash-Next post-reboot recovery Stage B1 result

Date: 2026-08-28  
Status: **passed; host recovery chain complete**

Stage A3 and Stage B1 both passed their frozen recovery gates. The known-good
TP4/EP4/eager/MTP0 server loaded all 131 local-NVMe checkpoint shards and
became healthy. Its sole authorized cache-cold request returned HTTP 200,
normal stop, exact `OK`, the frozen output hash, exact 17/2/19 usage, and zero
cached or created cache tokens. The observed 6.584560-second request time is a
diagnostic only and carries no speed credit.

The descendant-aware supervisor returned zero. Port 19667, the complete server
process group, compile path, and RPC path were absent after shutdown. All four
cards rediscovered at 42.875--42.879 MiB, and all five benchmark/GPU locks were
free. The bounded journal contains no B70 reset, fault, timeout, or fatal event.

The storage caveat remains real: checkpoint loading produced four corrected
APEI/NVMe receiver-event records for `0000:01:00.0`; the first also named
`NonFatalErr`. No I/O error was recorded and the model canary completed, so
this does not fail the preregistered B70 recovery criterion. Future local-NVMe
model runs must continue to retain and inspect their bounded journal rather
than calling the host literally event-free.

This result grants no speed, quality, coverage, matrix, deployment, package, or
LocalMaxxing credit. It completes the post-reboot host recovery prerequisite
and authorizes only one separately preregistered Qwen3.8 AutoRound INT4
correctness diagnostic with its own source, model, storage, output, and stop
rules.

Structured receipt:
[`../data/20260828-post-reboot-recovery-stage-b1-result.json`](../data/20260828-post-reboot-recovery-stage-b1-result.json).

External root:
`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/post-reboot-recovery-qualification-20260828-stage-b1`.
