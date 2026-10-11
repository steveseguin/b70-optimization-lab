# Independent review before any device window

Three subagents independently reviewed the event chain and integration. None
ran a device binary or changed protected packet13/14/15 files.

- **Non-GEMV adapter review:** packet15 descriptors and pointer arrays are copied
  into submitted operations before stack temporaries disappear. All allocations
  remain arena-owned through terminal completion. Control/score/probability
  scratch is serialized by the owner tail. Sticky-error merge never clears an
  earlier error; GEMV status checks feed the same flag. Miniature GDN/QSA now
  use dimensioned parallel equations instead of an interpreter fallback.
- **GEMV/owner review:** one owner ledger makes peer-copy dependencies valid
  across both shared-context queues. Queue selection happens synchronously
  before submission; native descriptors capture the selected pointers. Layer
  snapshots remain live through token readback. Profiling precedes retirement;
  streaming releases follow drain. No lifetime race found.
- **Window/provenance review:** W1 binds the existing completed packet13 receipt;
  W2/W3 bind a successful W1 on the same boot and binary, plus frozen oracle
  tokens and first-eight step fixtures. Fresh repeats bind context and dispatch.
  Native configuration and CPU qualification receipts are checked, as well as
  source, binary and input hashes before/after execution.

Findings fixed: bounded the owner destructor's ordinary drain to 60 seconds;
separated prompt timing rows from generated rows; selected context 256 for
87+63 positions; added native owner-card/config identity; rejected masked device
selectors; added CPU-gate receipt checks; bound build sources before/after
compilation/tests; bounded readelf; checked CPU priority and binary identity;
refused a signal received before child launch. The host build uses two numeric
threads, with unchanged independent per-row arithmetic.

Additional meaningful CPU owner test: 7 checks including premature dependent
completion, busy allocation release, premature retirement, stale event use,
and 5,000 queued copies without an intermediate wait. Original four retirement
checks also remain. Native event behavior is still a device gate.

Remaining observations are explicit in README/WINDOW: five forward plus two
return copies form two logical handoffs; first-eight fixture capture adds work
inside the measured span; transfer completion wait overlaps compute; host_waits
counts bounded event waits, not already-idle synchronization calls; unrecoverable
native faults retain ownership for the coordinator. The reviewer did not
claim that successful compilation proves peer access, fit, device parity or speed.

Final audit corrected a planner-only error: expanded split4 returns one native
launch, not two. R5 totals are 2,157 core / 3,371 parallel, 264 below the
previous static count. Runtime counters already counted correctly. The final
binary was rebuilt and both full CPU gates were rerun after the correction.

Receipt review also set oracle_exact=false before throwing on a layer mismatch;
the error and passed=false already rejected it. A just-started CPU gate was
stopped once to include this reporting fix in the final rebuild.

A deliberately wrong layer-0 fixture is rejected in both core and parallel
modes with passed=false, oracle_exact=false and the exact first-layer message.
The two checks are retained in [cpu-mismatch-rejection.json](cpu-mismatch-rejection.json).

R5 was also explicitly selected for all 12 miniature numerical cases (both
non-GEMV modes, one/two cards, 1/3/8 generated tokens): 46,476 values match
the frozen outputs already checked against independent NumPy equations.
[Receipt](cpu-r5-mini.json).
