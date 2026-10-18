# Packet130 boundaries

- Never infer a speed gain from packet128b's wait budget. Layer fences can cost
  rank0 time. Measure both complete control/candidate arms and all outputs.
- No extra rows/layers, compressed KV, new arithmetic or speculative input to
  the suffix. Read only rank1's sequence-bound verified normalized hidden state.
- Never apply target cancellation or launch-count observers to private suffix
  commands. An early verification must not silently shorten the baseline's
  speculative half; retain the entry-confirmation predicate until half return.
- Clear the schedule at each native request, after proving it completed. Native
  mailbox sequences restart when the request mapping is reset.
- Copied v5 drain helpers may predate packet124c. The clock-crossing regression
  failed on that copied helper here; both new copies must have the clamp.
- A source-sealed CPU mock is not full-model device equality or a speed record.
  Device smoke and bracket are pending. No candidate is adopted from a CPU gate.

- The Intel CPU IPC launcher needs the explicit installed compiler library
  directory for `libiomp5.so`. The closed-environment first attempt failed at
  the loader; the corrected path and library hash are bound to the passing gate.
- CPU preparation is closed in [the closeout](CPU-PREPARATION-CLOSEOUT.md).
  Continue with the sealed smoke/bracket, not another unmeasured scheduling claim.
