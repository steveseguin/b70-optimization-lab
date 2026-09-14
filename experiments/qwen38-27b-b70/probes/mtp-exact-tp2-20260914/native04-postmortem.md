# Native04 stopped on GPU faults

**All further GPU work is halted. No speed or quality qualification passed.**
The complete [incident receipt](native04-postmortem.json) binds raw files,
precise kernel timestamps and the inactive follow-up below. Native04's frozen
snapshot, binary and raw results remain unchanged.
The current launcher has an unconditional native-execution quarantine with no
override; changing the output directory cannot bypass it. CPU-only admission
checks remain available. This guard does not alter the frozen incident recipe.

Both ranks saved twelve exact `[1,5120]` cases, including signed zeros,
subnormals, cancellation, overflow and rounding. The next case disagreed only
on the payload/sign selected when both inputs were NaNs. These partial matches
belong to a faulted attempt; they do not qualify the operator. No timings or
larger shapes completed, and no model requests ran.

Both workers wrote the quality-rejection traceback around **18:30:41.774 UTC**
and entered the general `os._exit(70)` failure path. The first kernel fault was
recorded at **18:30:41.795853 UTC**, about22ms later. Both B70 copy engines
reported invalid fault responses and resets; one also reported a memory CAT
error. The controller latched the GPU fault and confirmed that the container
had already stopped. It did not send a stop command.

This timing is consistent with a process-exit lifetime race, but **does not
establish the cause**. Exact worker exit timestamps and allocation-address
ownership were not captured. Candidate copies, XCCL internal operations and
driver lifecycle behavior remain possible sources. The source waited for
local copy/add events before checking outputs; that alone does not prove all
driver or collective internal work had retired.

A specific weakness is established independently of causality: an ordinary,
mutually acknowledged quality mismatch followed the same abrupt exit path as
an unexpected device failure. It skipped the explicit peer-import retirement
protocol. The inactive [helper](quality_retirement.py) and
[integration patch](quality-retirement.patch) separate those cases. With all
events completed and healthy peer agreement, they close imports, acknowledge
both closures, return export handles, then free original storage and perform
normal process-group teardown. The outer controller still bounds teardown.
Four CPU ordering/refusal tests pass. The helper is not imported by the active
gate, is not included in the launcher snapshot, and has never run on a GPU.
Future integration must explicitly add the reviewed helper to the source
snapshot. It is not a remedy for device faults, unfinished events or a missing
peer; unknown-fault group termination still requires separate review.

The NaN discrepancy remains unresolved. The installed oneCCL2022.0.0 release
pins legacy backend `4ceafd15c03ce46f11eeaf91781a92afebd3cecf`, matching the
available allreduce source. Compiled operand-selection semantics have not been
established. No test was removed, no fixture-specific result substitution was
added, and no arithmetic change is proposed as qualified. Any future arithmetic
candidate must retain all existing cases and add NaNs in both operand positions,
both signs, quiet/signaling forms and varied payloads before further timing.
