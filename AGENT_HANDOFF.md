# Repository Handoff Pointer

This compatibility path no longer carries a second copy of live workspace
state. Use these sources in order:

1. [`CURRENT.md`](CURRENT.md) for the loaded service, active lane, protected
   work, and immediate next actions.
2. The active lane handoff linked from `CURRENT.md` for detailed resume context.
3. [`docs/model-effort-index.md`](docs/model-effort-index.md) for durable model
   lane discovery.
4. [`results/scoreboard.md`](results/scoreboard.md) for representative verified
   performance.

The former mixed Qwen, Gemma, and MiniMax handoff remains available in Git at
commit `95b4ca413` (`git show 95b4ca413:AGENT_HANDOFF.md`). It is historical
evidence, not an authority for what is live today.

When handing work to another agent, update `CURRENT.md` only if cross-repository
live state changed. Put experiment chronology in `notes/` and technical resume
details in the relevant lane handoff or result packet.
