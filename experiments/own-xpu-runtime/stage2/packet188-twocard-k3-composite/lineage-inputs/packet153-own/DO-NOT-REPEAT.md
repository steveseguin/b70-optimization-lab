# Packet153 boundaries

The repository-wide snapshot/descriptor/rotation search covered every
DO-NOT-REPEAT.md and notes directory before implementation.

- Packet62 and packet131: do not rotate QSA/scratch or drop logical old-spare
  state. This packet retains their exact bytes and all original bank rules.
- Packet121 and packet144: miss-only transfer overlap is not the every-cycle
  capture lever. No skip-on-redo or restore-on-miss speed estimate is reused.
- Packet131: the production flat copy already uses two submissions, not 984
  separate GPU copies. Static removes its upload and host construction only.
- Packet150: asynchronous host snapshot time is not completed GPU copy time;
  duplicate service does not prove removable work. Keep original host scopes.
- Packet23/22: metadata is prepared before recording, never on a first token.
- Packet136: preserve shared oracle binding, drain fix and native getrlimit;
  CPU source caps must never reach a device launcher.
- Immutable table bytes must survive BOTH zero_private and request_reset.
  The CPU proof checks table bytes separately from logical model state.
- The protected-active negative control must poison pre-capture A, not the
  speculative C that rollback legitimately discards.
- Missing rank streams, native correction traces or comparison scopes fail
  smoke immediately. Synthetic report rehearsal never counts as device proof.
