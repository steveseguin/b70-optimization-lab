# Packet 57: attribution inside the packet 56 engine

This packet measures where the two-card pipeline spends time. It keeps
packet 56's numerical kernels, 91,392-row draft prefix, 23/25 target split,
rank-1 draft, BF16 KV and packet 49 target oracle. It is **diagnostic only**.
The current measured record remains packet 56's **46.962697 tok/s**.

The existing receipts put rank 0 on the critical path most often. They do
not contain usable per-layer or draft-kernel event measurements. The new
instrumentation fills those gaps inside actual WS-style requests; isolated
operator savings are not treated as engine savings.

- [Timeline](TIMELINE.md): reproducible analysis of packet 56, 49d and 49c,
  including waits, limits on idle attribution and conditional split estimates.
- [Next levers](LEVERS.md): current ranking, explicit bounds and measurements
  still needed from the diagnostic run.
- [Coordinator window](WINDOW.md): exact command, duration and gates.
- [Independent review](REVIEW.md): observation-only changes and admission checks.
- [Task note](../../../../notes/2026-10-17-own-runtime-packet57.md).

Only the new packet's documented entry points are operational instructions.
Copied historical helpers preserve its lineage; they are not alternate
launch instructions. Parent packets and their seals remain unchanged.

Preparation is CPU-only, low priority and serial for compilation. No device
window is run here. Packet 55's cards-2+3 route window remains protected;
the later coordinator run must also pass host-memory and ownership admission.

Event instrumentation can change overlap. The same diagnostic window includes
a packet-56-style timing control and an instrumented arm, both compared with
the same oracle. Scaling the measured breakdown is a sensitivity analysis,
not a recovery of an unperturbed GPU timeline or a speed claim.
