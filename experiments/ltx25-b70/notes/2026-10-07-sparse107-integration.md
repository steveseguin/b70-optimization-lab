# Sparse sampler transport107 integration

106 remains healthy and idle; its57-request plan is consumed.107 is a necessary
controlled application successor, not a change to the running106 packet. No107
GPU request, source materialization, application reload or106 raw retirement
has occurred at this CPU review checkpoint.

## Purpose and fixed workload

The106 counters are exploratory and globally incomplete. Do not rerun merely for
a green accounting flag.107 directly observes actual sampler transport/fill work
before selecting a numerical-path optimization. Candidate-phase observations do
not establish a steady-state bottleneck or promise a speedup.

The standalone107 plan keeps all ten fixtures,640x384 geometry,25frames,
24playbackFPS,8+3steps,nativeBF16,W2/B1/shared pools,23/25 placement andxpu2
replica decoding. It admits20native,14candidate,14timed-fast and9setup requests:
57attempts,50captures,4GiB runtime allowance above50GiB. Source construction
has its separate384MiB allowance. No control block or passive collector.
Exact native repeat/candidate/timed four-tensor gates remain mandatory.

## Frozen injection contract

The source-bound contract is the reviewed `sparse_transport.py`, exact106
`sparse_transport_overlay.py`, `transport_gate.py` and integration code, all
included in the input inventory and sealed manifest. Independent prototype files
and synthetic tests preserve review provenance. The original standalone pending
descriptor is retained as the earlier design; this note and source implement it.

At most one eligible actual candidate job per registered worker0/1 may be selected,
from physical99907104..99907109. Selection matches the actual Thread object and
ident against the registered pipeline worker list. Both workers are required;
there are no substitute jobs, extra requests or retries. Only the second observed
forward in each denoising stage is instrumented. Forward ordinal is one-based2.

Actual img0/1 transport at block23 and out0/1 transport after block47 get D2H and
H2D event pairs on the existing owning streams. CPU clocks bracket the existing
source-event wait and destination allocation. The wait includes preceding work,
so it is not D2H latency. A nonempty fill call gets one pair plus actual copied
component count and physical target bytes, honoring expanded fill targets and
identity skips. Two partition spans cover replay0..22 and23..47; they include
intervening fills/submission gaps and are not isolated kernel time.

Each selected worker has at most108 operations/232 recorded events under the
validated topology. The allocation cap is128 operations and128 events per device
per worker:256 events per worker,512 across both. Whole pairs are reserved before
recording. Event pools remain owned even on failure. At most64 actual sampler
jobs enter the audit, and each durable phase evidence envelope is capped at1MiB.
No new synchronization, stream changes, numerical operations, copies, allocations
of model tensors or replay ordering changes are introduced. Event objects may
initialize lazily on first use. Elapsed reads occur only after the original sampler
body returns, proving its existing drains and sentries completed. Original
backend/model exceptions propagate; the outer finally clears thread-local state.
Invalid topology, order, caps or coverage globally disables further timing and
marks the diagnostic invalid without altering the model's ordinary execution.

At the candidate barrier, the existing pipeline is quiescent and completed tails
are recorded/retired. Their original sampler fingerprints remain. The independent
gate compares all actual input/output sentries and trace fingerprints with the
helper execution census, including uncollected tails, then closes selection.
It maps relative emitted positions to physical producer IDs; submitted requests
are not assumed to equal sampler jobs. Both13- and14-job synthetic cases pass.
The timed barrier requires zero timing events for every actual timed job. Dormant
hooks and bounded CPU bookkeeping remain: this is not a hook-free runtime.
Both diagnostic receipts stay separate from exact model-quality proof. Preserve
and hash them in closeout; the tensor proof alone does not reconstruct tracing.

## CPU validation and review

257 author-runtime tests passed in39.964s;35 helper/overlay tests passed in0.409s.
Independent gate review passed12 real-helper synthetic controls. Source tests
verify pre-overlay numerical equality with106, unchanged original sampler body,
unchanged numerical copy/allocation/replay/sync sequences, expanded fill bytes,
worker ownership, phase boundaries, exception behavior, and worst-case caps.
The full source bindings and inventory are in
`data/resume-20261007/sparse107-cpu-validation.json`; actual filename reservation
is in `sparse107-reservation.json` in that directory.

Review corrected an initially excluded runtime helper, relative-vs-physical clip
mapping, zero-based ordinal metadata, global diagnostic failure handling, and
strict evidence identities/types before launch. All failing cases remain tests.
No host power, memory, swap, cache or driver settings changed.

## Next operating sequence

Commit/push reviewed source, build/seal107 while106 remains idle, verify fresh
namespace/storage admission, then one necessary controlled106 application stop
with exact identity and clean journal evidence. The reviewed post106 duplicate
helper may reclaim only its fixed40 whole-file matches after fresh full106 proof
reconstruction and stopped-owner evidence. Preserve all keepers and restoration
receipts. Admit4GiB above50GiB freshly, launch107 once, bind client contract and
run its finite campaign. No automatic restart/retry and no requests after faults.
Retain the successful application and continue from measured evidence.
