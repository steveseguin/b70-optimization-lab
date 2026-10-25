# Isolated rolling socket bridge

`socket_bridge.py` adds actual transport integration to the event-level adapter.
It accepts existing guarded stage owners; it has no CLI, process creation,
native launch plan or device access of its own. No active controller imports it.
Current pending-provider proof files remain unchanged.

The bridge reuses `PendingStage` and the existing target ROW/ACCEPT/ABORT,
final-record and recursive-provider codecs. A single `select` loop services
partial writes and fragmented replies on all owners. Stage zero's logical
auxiliary reservation maps to the same global wire sequence in the actual
provider request. Its original accepted ROW ticket/flag and owned final record
are checked before transport. The final record's marker, immutable metadata,
112-byte handoff and hidden bytes are validated by the existing decoder before
the scheduler receives the independently owned parent identity.

Only decoded actual provider guesses are published as speculative hypotheses.
Reference/oracle configuration keys are refused; the bridge never loads a
reference. The final target's actual output remains the sole authority for
acceptance and correction. Target buffers are copied into owned publications
before another command can overwrite a shared slot. `final-records.jsonl`
retains the validated 360-byte record, its SHA, original ROW/ACCEPT tickets and
hidden SHA/extent; provider batches bind the corresponding parent and commit. The provider reply must
preserve its reserved physical/logical cursors and exact pending row IDs.

All reserved commands remain owned through a cancellation request, including
requests with unsent bytes. Explicit cancellation closes new generation,
finishes already reserved work and drains its frozen verified prefix/suffix.
An in-flight provider still requires its complete validated reply. The unused
parent lease may be abandoned only under cancellation, as described in
`INTEGRATION.md`. `cancelled_provider_incomplete` is a conservative exclusion
from completed-request qualification, **not a measured state mismatch**. In
particular, a parent-only lease can be abandoned even when provider position
already covers the eventual final target prefix.

The future lifecycle adapter must handle cancellation distinctly: it must not
invoke normal full-state DUMP/FINISH attestation on a provider-incomplete prefix.
It should use the existing cooperative stop lifecycle. Normal EOS/cap completion
must retain full canonical pair conservation and independent final state checks.
This isolated function does not grant native RESET support or implement that
outer lifecycle branch.

Four additional test families use real socket pairs with fragmented responses
and delayed providers on 2/4/6 stages. They check actual codecs, shared sequence
numbers starting at 500, output/history parity, misses, complete terminal trace,
cancellation, invalid provider serial, truncated reply, invalid final marker,
and pre-owner oracle rejection. Only worker arithmetic is synthetic. They do
not establish GPU correctness, native survival, speed, clean-host deployment,
or a runnable release recipe.

```sh
PYTHONPATH=engine/planning python3 -m unittest discover \
  -s engine/planning/rolling-provider-next -p 'test_*.py' -q
```

All 15 tests passed before the first socket review. The first test run exposed
only a test comparison mismatch between JSON arrays and in-memory tuples; the
trace is now compared after JSON normalization. The earlier cancellation defects
and their fixes remain documented in `INTEGRATION.md`. Source hashes and exact
scope are recorded separately in `socket-cpu.json`.
