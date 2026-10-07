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

## Sealed source and predecessor stop

Source commitf4a0b7dff is pushed. Fresh384MiB build admission passed above50GiB;
107 full source closure verified with manifest
`36348968dd0a5ee3ce2aeda24d24f614823cae5c00050a3b3b72cfe9ad15ff38` and inventory
`40c4ccb7f2a586d37fdbcf885f256523bcbd8c2b16d88b6a186d3019cdedb3fa`. Constructor99b PID3129897 was absent.
106 remained untouched during source construction.

106 received oneSIGINT after two idle queue/tail/preview observations5seconds
apart, exact PID/start/boot/identity checks and clean kernel journal. It exited
at2026-10-07T21:17:16.424803+00:00; all render nodes were unowned afterward. The single
four-card postflight passed at2026-10-07 21:17:42 UTC, with zero earlier/new faults.
The40-file106 retirement helper now reconstructs the full sealed proof before
any deletion. Stop receipts are under`sampler106-closeout/`; models and all
restoration keepers remain protected.

## Storage transition completed

The reviewed40-file retirement completed after two fresh106 full sealed proof
reconstructions. PlanSHA`35042e3c1f28c9605c122298326f9bacc9000b72edde26e0d25212bc47863d0b`;
receiptSHA`37d365a57b6fcdf3b7063a102faec8c6a0b0ed6caf91ab7180bb6a5de97d031b`. Reclaimed2.7801GiB with direct
105 native-p1 keepers and restoration maps. Fresh107 admission observed54.897GiB
free and50.897GiB after4GiB. No model or failed experiment removed.
[Restoration details](2026-10-07-after106-storage.md).

##107 startup refusal before model requests

The single107 launch at21:22:04UTC started PID3362138, ticks28195647, same boot.
Its first resolution-status GET returned500: `LTXGraphCaptureGate` was missing.
The application had logged that the graph custom node lacked NODE_CLASS_MAPPINGS.
The root builder incorrectly treated the canonical graph helper as a node mirror
and replaced the distinct graph registration wrapper. The sampler script really
is mirrored; the graph helper is not. Both root and independent review missed
that packaging distinction. CPU source/overlay tests did not execute registration.

No model request, client contract or campaign was created; standard queue and
history reads were empty. No kernel/device fault was latched. The failed sealed107
packet/run and full startup journal are preserved in place, with bound evidence
under`data/resume-20261007/sparse107-startup-refusal/`. The application remains
idle while the correction is prepared; do not modify its sealed source or append
requests. This failed packaging attempt is not model or performance evidence.

The author correction107b removes only the mistaken graph-wrapper replacement,
keeping the original99b wrapper which imports the modified canonical graph
adapter. It retains the same never-submitted107 plan/request namespace and all
trace/quality code, with a new packet/run identity and explicit CPU node-export
regression. No automatic reload or retry has occurred. One necessary controlled
reload will follow reviewed/sealed corrected source and fresh storage admission.

The corrected107b builder passed12 existing builder tests and5 new static
registration regressions. The actual original graph wrapper and its class export
are preserved, and the canonical instrumented adapter is imported. All other
node mirrors were independently checked against their actual parent scripts and
exports. The exact failed107 substitution is a negative test. Every previously
validated source except the builder and its identity test is unchanged; the new
validation binds that carried evidence and the focused tests. A fresh filename
scan confirms the never-used107 request namespace is still clear for107b.
