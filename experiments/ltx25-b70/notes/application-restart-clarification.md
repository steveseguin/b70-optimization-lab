# Application restart and continuity correction

On September 14 the user clarified that asking repeatedly about an application
restart and stopping optimization afterward was unwanted. The earlier agent
mistakenly turned the preference for a persistent process into an approval
barrier, then interpreted "just restart" as ending the broader optimization
task. It also used "server restart" without making clear that the computer
would remain running. These were workflow and communication mistakes.

The local and repository AGENTS instructions now preserve this clarification:
a necessary controlled application reload within authorized work is not a
blanket permission checkpoint. Continue the optimization task afterward. The
no-restart-chain, no host reboot/driver reset, no power/swap/page-cache changes,
and fault-halt rules remain intact.

The authorized transition stopped original PID24848 cleanly with one SIGINT.
An initial launcher bind probe encountered an unowned TCP TIME-WAIT socket and
exited before Torch import or GPU initialization. After observing its expiry
and a successful bind check, the unchanged launcher started PID75850 once.
The manifest and endpoint identity match; no computer restart occurred.
The failed preflight log and migration receipt are preserved externally.

The preregistered encoder-screen-01 GPU comparison now runs on PID75850.
Original quality, 256x256 output, 25 frames at24fps and 8+3 sampling steps remain
fixed. This note supersedes earlier statements that optimization must wait for
application-restart approval. The measured subsecond goal remains unchanged.

Operational follow-up for a future launcher revision: the port-availability
probe should distinguish a listening process from an expired application's
TIME-WAIT socket. Do not mutate the active immutable source packet to make that
unrelated cleanup, and do not restart the application to address it.
