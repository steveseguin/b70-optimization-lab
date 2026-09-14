# Native one-block gate facade

The inactive [node](../scripts/block_compile_node.py) now exposes
`LTXCompileOneBlockGate(model, mode, block_index=24, run_name) -> MODEL`.
The [CPU unit test](../scripts/test-block-compile-node-cpu.py) passed 14 checks,
with [receipt](../data/block-compile-node-cpu-01.json) and
[log](../data/block-compile-node-cpu-01.log). Its compiler, routing and startup
context are explicit spies: this tests mutation isolation, repeat bookkeeping,
receipts and rejection behavior, not actual compiler capture or GPU execution.
The process exited 0. The receipt binds both tested source files.

The [diagnostic follow-up patch](../patches/block-compile-node-01-to-02.patch)
adds per-output expected/actual byte SHA256 values, unequal-byte counts and
metadata equality to the first-stage checks. Structured comparison rows also
travel in `ComparisonError.rows` into `comparison_failure_rows`, including
metadata failures before assignment. The same unchanged 14 CPU checks passed
again in [receipt 02](../data/block-compile-node-cpu-02.json) and
[log 02](../data/block-compile-node-cpu-02.log), process exit 0. Node SHA256 is
`ba98268c89f52477d4641a15b2f8ea9e73f68cdd5fc683700ee50d98f706280e`.
The earlier source is recoverable by reversing the patch and remains in sealed
compiler packet 01. Prior receipts/logs and the test helper are unchanged.
This strengthens failure evidence without changing warm execution or admission
rules; the successor packet must bind the new node hash.

This implements the compiler boundary proposed in the
[integration plan](ltx-native-block-runtime-integration-plan.md), with two
subsequent root decisions: a nine-request screen (two eager boat controls,
compiled boat initialization plus boat/marble/bird/boat, two restored boat
controls), and direct native block comparison during the first compiled clip.
The root-owned packet builder/client and actual XPU screen remain separate.

The facade imports the unchanged effective adapter formed by ownership guard
followed by lifecycle-v2. It retains one candidate from the resident patcher;
all later requests must name that same original patcher. Eager mode returns the
original. Restored mode returns the measured adapter's restoration clone. No
registered weight or forward method changes, no output cache, and no component
reload or server control are introduced. Block 24 is fixed on XPU1 in the 21/27
split. Both guider model edges must use the facade's single output.

The compiled route retains its exact class, native routing and lifecycle guard.
Only its already-created compiled callable is wrapped by the diagnostic gate.
On the first invocation of each of two native stream signatures, the wrapper
creates independent eager and repeat input copies before execution. Native
`forward` mutates its streams in place, so compiling the already eager-mutated
input would be invalid. The original streams receive the first compiled
execution, whose output is returned only after eager/compiled and
compiled/repeated-compiled equality and finiteness pass. Unexpected aliasing or
noncontiguous stream inputs fail instead of silently changing their semantics.
Other native arguments and transformer metadata are passed intact. Warm calls
execute the compiled callable once.

Comparison uses CPU byte views, preserving signed-zero distinctions and
rejecting matching NaNs. Failure receipts retain per-stream equality flags and
the error; large tensor dumps are not added. No failing result proceeds to the
next block. The candidate latches failure locally, while the root client must
halt all subsequent requests on any failed request or device fault.

Each compiled request has exactly eleven allowed block dispatches. The first
dispatch inspects actual registered state and requires 84 native BF16 tensors,
773,349,760 bytes, on XPU1. No casting is performed. At most two input signatures
and two compiled graphs are admitted; graph breaks or unsupported-operation
counters reject the screen. Counters are observed without resets. A failure to
complete eleven calls prevents another compiled/control transition.

Receipts are exclusive files in `<server-run>/compiler-<run_name>/`:

- `request.json`, schema `ltx.compiler-request.v1`: setup status, mode/index,
  original/candidate identities, source/options, model/startup identity hashes.
  Its `passed` flag means setup succeeded, not that a video passed.
- `call-01.json` through `call-11.json`, schema
  `ltx.compiler-block-call.v1`: call identity/status, stage signature, cumulative
  counter deltas and qualified-stage count; first-call census; direct
  comparisons only when `stage_check` is true. Initializer calls 1 and 9 should
  qualify the two unchanged 8+3 stages. Later requests reuse those qualifications.

The client must still require all eleven successful calls, both stage
qualifications, matching source/process identity and exact equality of all four
full-clip oracle archives, including initialization. The eager comparisons and
first-use compilation exclude initialization from any warm timing claim.

The new facade object in callback metadata has not been tested with real
Inductor capture. The preceding real CPU capture qualified the adapter and
lifecycle object, not this additional wrapper. Native XPU capture, full-width
compiler memory, actual-input contiguity and alias assumptions, and full-clip
parity are the next experimental gate. Runtime checks and per-call JSON writes
add unmeasured overhead to warm timings. Restoration is dispatch-only and does
not promise compiler-memory release. No existing packet, server, model, prior
compiler receipt or measured source was changed by this facade task.
