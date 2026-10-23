# Authority for the host row-capture proof

This is a proposed CPU ownership proof using the actual inherited Device,
Arena, PreparedCompute, CopyEngine and GNU HOST_ONLY submission objects.
Synthetic data and small adapter operations do not establish full-model
arithmetic, device scheduling, performance or an implemented layer-major Engine.
[Input pins](authority-inputs.json) identify the source and object authorities.

## Existing implementation

The tracked p181 lineage `native/generated/owner.cpp` is the owner source
pinned by its build receipt alongside GNU owner.o. The same owner object is
in p198's successful host link. The original p58j GNU adapter object still
matches the p198 inherited adapter object byte-for-byte; its dependency file
points at the retained checked adapter source. The historical GNU build
receipt also pins the raw source. Reuse these objects with p198's frozen
checked headers rather than silently compile current raw source against a
different header closure.

`Device::capture_operation` copies allocation IDs and resolved raw pointers,
records owner/generation, and asks the backend to retain an owned operation.
The templated HOST_ONLY compute path clones the concrete operation before
capture. The p198 Host backend retains that shared HostOperation and another
copied pointer vector. Changing or destroying the caller's maps, ID arrays or
Spec must not redirect an already captured command. This does not freeze
buffer contents: intentional in-place writes remain visible when it is issued.

Captured commands do not own allocation leases. Arena owns storage. Releasing
any allocation changes the generation and invalidates all prepared commands;
release while work is pending is refused. Device destruction/recreation at the
same address cannot resurrect a prior generation. The existing prepared
invalidation source is useful baseline evidence, not a substitute for the
new two-row composition proof.

Capture validates local dependency ordinals but PreparedCompute stores no
replay dependency graph. `issue` invokes the retained submit closure; HOST_ONLY
runs the operator synchronously, then produces a marker. Host inherits LifetimeMock, which inherits MockDevice: event, queue and
context completion are the existing deterministic simulated backend model.
MockDevice::copy stores a real memcpy closure; Host::copy immediately calls
finish(e), which runs it after checking simulated dependencies. CPU arithmetic
and copied bytes are real; native event provenance is not exercised. The
proposed proof must order real issue calls and verify owned completion in that
CPU model before publication. It must not infer asynchronous device safety from two integer
completion counters or from the logical binding map.

## Small actual adapter seam

A bounded sequence can use `Special::begin` for each row's position bound,
`Special::ple_hash` for token/history/metadata to sixteen IDs, `Op::conv` for
distinct row inputs with one shared recurrent history, and `Op::hc_combine`
for distinct row streams. PLE hash is a Spec special, not an Op enumerator.
Use the actual `packet18::submit_parallel` capture path and its existing
HostOperation types. Geometry and gains must be explicitly synthetic. The
host fallback or tiny operation path is not proof of selected GPU arithmetic.
Some CPU operators use local work arrays instead of the bound device scratch.
Sharing that allocation ID alone does not prove scratch contents are consumed;
a content-sensitive scratch test or an explicit scope limitation is required.

Two captures must resolve distinct token/position/streams/input/output IDs
and the same intended persistent state and scratch IDs. After capture, mutate
the caller maps to decoy allocations and mutate the source Spec to an invalid
geometry: execution must still touch the original captured bindings and
operation. Keep decoy bytes unchanged and inspect argument blocks, including
cloned operation bytes where available. Independently compare a serial eager
execution with the prepared sequence using the same synthetic starting bytes.

## Meaningful ownership and publication gates

1. Capture submits zero work and does not change state or streams. Destroying
   caller arrays/Spec after capture is safe; a deliberate live-input content
   change is consumed. Misbinding the two row streams is detected by unequal
   row data and distinct expected outputs, not merely by handle inequality.
2. Shared history carries row0's update into row1. Both rows must change state,
   and resetting history before row1 must yield a different result. Scratch
   consumers finish before reuse. Owned event wait/complete is used before the
   final copy; a simulated uncompleted marker must not authorize publication.
3. Canonical streams, token, position and token-history descriptor remain at
   their original bytes while the chunk is partial. After both successful
   rows and host-backend completion, CopyEngine publishes the final row's
   streams and the complete descriptor. Wait for that copy too before claiming
   publication complete. These multiple copies are not atomic: a later copy
   refusal can leave some canonical bytes updated. Such a failure must poison
   publication and refuse success/retry without claiming rollback. Old per-row
   commit must only touch row-local position.
4. A guard failure after row0 stops the chunk permanently, leaves canonical
   publication unchanged, refuses row1/commit/retry, and admits that shared
   history may already be partial. There is no rollback claim. This can be
   tested separately from an exception inside a backend operation.
5. A backend operation exception makes Device sticky-faulted. If later drain
   and teardown succeed, the owner receipt remains failed-drained/exit1; it
   cannot be called a normal success. If teardown cannot prove completion,
   preserve retained ownership and the primary failure. Do not modify the
   inherited cleanup rules to make the fixture pass.
6. Release/reallocate and explicit invalidation must reject stale captured
   bindings before execution. These invalidation checks belong in a separate
   owner instance so a negative test cannot invalidate the successful proof.

The experiment must retain source/object hashes, compile/link command,
argument maps, complete numerical/state comparisons, ownership receipts and
failed attempts. It starts no model owner or service and reads no model
weights. A successful CPU result still leaves real Engine map rebuilding,
state-bank/FP32-tag handling, actual device dependency provenance, complete
48-layer execution and checkpoint integration as separate work.
