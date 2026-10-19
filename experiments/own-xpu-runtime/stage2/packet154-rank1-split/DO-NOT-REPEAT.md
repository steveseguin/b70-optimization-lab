# Packet150 boundaries

- Do not profile events created during graph capture. Use the host scopes and
  redundant replay versus skip arms defined in README.md.
- Never skip real token preparation, snapshot state, target head work, verifier
  or required peer/draft waits to create a speed claim.
- The snapshot duplicate belongs before spare-bank rotation; token replay must
  restore the original host histories before repeating the same token.
- Snapshot host submission is not completed GPU copy time. Subtract nested
  replay scopes and retain the unassigned outside cost and excluded boundaries.
- Use 63 intervals for the 64-token diagnostic. It is never a 1–100 headline.
- A cost above 0.4 ms/cycle is not proof of removability. Keep all target-output,
  draft-proposal and per-prompt acceptance checks, plus cancellation diagnostics.
- Preserve packet149's fixed native-trace reader and its retained-log regression.
- Only the coordinator can queue the lane-B proposal after the split marker.
  Any shared-correction work has separate sources, evidence and readiness.
