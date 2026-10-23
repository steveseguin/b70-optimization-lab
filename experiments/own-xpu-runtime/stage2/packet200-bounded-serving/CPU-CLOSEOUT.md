# Packet200 bounded coordinator: CPU result

## Question and identity

Can the tested baseline native chat components be joined into a bounded owner
with explicit admission, diagnostic handling and clean resource ownership?
This packet retains the frozen p198/p199 native identity and prepares a
sequential16-request session. It does not change the model or native kernels.

## Outcome

The additive coordinator passes26 CPU checks and independent source review.
Its outer-window contract passes11 checks. The root repeated both sets:
[37-check receipt](evidence/root-combined-cpu.json),
[worker review](evidence/independent-worker-review.json), and
[window interface review](../../ops/packet200-window/interface-review.json).
No native model, device, service, queue or application transition was executed.

This advances the [serving objective](../../../../docs/own-xpu-runtime-objective.md)
from separately tested components to one explicit owner/resource lifecycle.
The tested real-model predecessor remains
[packet199's six-turn HTTP result](../packet199-chat-parking/RESULT.md).
Synthetic packet200 requests do not add model correctness or speed evidence.

## What worked

The worker composes the frozen baseline native binary, profile, checkpoint
store, parking, chat interface, attached lifecycle and bounded pipe capture.
It permits at most16 sequential loopback requests, context4096, at most512 new
tokens per request, full BF16 state and512MiB parking. It retains the baseline
21,552,729,600-byte expert cache; this is not the later max23/diet record build.

Launch uses one intercepted `Popen` path and unlimited address space. Diagnostics
start before readiness waits. Helper threads use their own lower priority and
helper cores, leaving native launch placement unchanged. The actual OS-pipe
test joins the real diagnostic reader/capture and verifies exact stored bytes,
EOF, ended threads and closed endpoints; the owner itself remains synthetic.

Normal completion requires matching native request/control counts, no pending
reply, one model load, exit0, diagnostic completion and physical-drain checks.
A durable pre-completion receipt precedes reservation completion. The control
writer remains open for the final guard calls; a final acknowledgment and
successful worker-unit exit are separate restore prerequisites. A failed final
write after physical completion remains an evidence failure, without inventing
retained ownership markers that have already been removed.

Incidents preserve the original exception, halt intake and permit one outer
cooperative SIGTERM. Uncertain spawn, retained owner, pipe or capture thread
keeps resources and coordination held. A refused launch precondition does not
pretend that a process might have started. There is no retry, hard kill,
automatic restart or failed-request recovery.

## What failed or remains uncertain

Review corrected completion ordering, raw fault-slice persistence, import
origins, native counters and deterministic launch-refusal handling. Earlier
candidates and a test-fixture failure are preserved under `lineage/`.
The missing-manifest regression now uses an isolated temporary path, so creating
a future operational manifest cannot accidentally send that test into preflight.
The prior root test receipt is linked from the current combined receipt.

Storage admission remains a monitored768MiB forecast above the27GB root floor.
It is not a hard bound on all native/driver writes, and polling cannot guarantee
the floor against an in-progress write burst. Frozen profile readiness flags
remain false. The default initial idle origin is the pre-launch timestamp;
loading consumes part of that first240-second idle interval. The separately
reviewed mapped-clock adjustment is optional and has no real-owner qualification
yet. Absolute deadlines are unchanged.

## Evidence and patches

The CPU plan uses an existing private0700 staging parent with absent `output`
and `checkpoints` children. The source/identity check covers231 profile/worker
files and20 inherited topology pins. The
[actual plan](../../ops/packet200-window/actual-cpu-plan.json) and
[contract receipt](../../ops/packet200-window/actual-cpu-contract.json) remain
CPU descriptions, not operational admission. No execution manifest was created.
The source delta is additive: [worker](device_worker.py),
[worker tests](test_device_worker.py),
[window contract](../../ops/packet200-window/window.py) and
[contract tests](../../ops/packet200-window/test_window.py).

## When to revisit

Add and review the execution adapters around this frozen worker and contract,
then bind their source closure and live checks before any device window.
The worker CLI in this result accepts only read-only planning. The existing
three restore28 applications stay in place during preparation.
