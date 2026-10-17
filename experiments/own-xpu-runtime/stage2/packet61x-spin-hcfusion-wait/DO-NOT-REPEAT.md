# Packet61x boundaries

- Never edit or reseal packet61 or packet56x. This is a separate candidate.
- Do not enable sleep20 or restore 1 ms device polling in this packet.
- Keep packet61 kernel sources and linked kernel objects byte-identical.
- The wait change covers mailbox, device and pending-draft callback waits.
- Keep deadlines, cancellation, peer abort and progress callbacks intact.
- Use the lean build script; copied historical CMake files are not this recipe.
- CPU checks and screen admission are not full-model quality or speed evidence.
- Preserve packet49 oracle, packet56 target fixtures, full 16-bit KV and current
  submission-floor checks. Screen results cannot qualify a record.

- A fixture directory existing does not establish input readiness. Require the
  full `check_inputs.py` closure and explicit K1/K2 fixture paths; preserve
  stopped outputs and use only the registered fresh chain. See
  [input repair closeout](INPUT-REPAIR-CLOSEOUT.md).

- **2026-10-17 — KD host scratch boundary:** source-local `P/build` is not the
  external chain build root. Check every write/scratch path before launch;
  never rerun the passed early windows or erase the stopped chain to fix this.
  [Repair and strictly pinned resume](KD-RESUME-CLOSEOUT.md).
