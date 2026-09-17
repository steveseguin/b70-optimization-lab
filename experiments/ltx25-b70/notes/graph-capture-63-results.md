# Packet 63: the forward-timer arm was refused by the patcher guard; packet 64 reorders the arms

*2026-09-17 04:29–04:32 UTC, server PID 4937, boot `09862e00…`.*

The warm clip passed its oracle. The first arm, `pipe-fwdtimed`, registered
a diagnostic DIFFUSION_MODEL wrapper (sync, call, sync, record wall), and the
graph-capture gate's patcher validation refused it: it admits exactly the
shard-transfer wrapper plus the concurrent-CFG wrapper and nothing else
(`ltx_graph_capture.validate_patcher`, "Foreign model wrappers are
unsupported"). That guard is correct as written; the timer had simply not
been added to its whitelist, and the direct-call packet tests never exercise a
live patcher. The gate's failure latch is sticky by design, so every
remaining arm on that server would have been refused; one SIGINT stopped it
cleanly after 3 s.

Fix (committed): the guard admits one extra DIFFUSION_MODEL wrapper only if
it is the single function named `timed_diffusion_model`. Packet 64 carries
the same arms with the lever arms first (`pipe-fasttimed`, `pipe-fast`,
`pipe-up-save`, `pipe` control) and the diagnostic `pipe-fwdtimed` last, so a
diagnostic refusal can no longer cost the levers their server.
