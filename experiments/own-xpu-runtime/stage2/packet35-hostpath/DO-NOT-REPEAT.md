# Packet 35: do not repeat

This index records closed implementation mistakes and unqualified approaches.
No device experiment ran in this packet. See [CLOSEOUT.md](CLOSEOUT.md) for scope.

| Arm or mistake | Outcome / retained evidence | Revisit only when |
| --- | --- | --- |
| Disable a qualifying fusion merely because a member also won | Rejected. Compare fusion time with the sum of selected member times for every workload. Historical regression restores HC, GDN A/B and both FFN formats. `k2-selection-regression.json`. | New matched measurements change the comparison; never skip it. |
| Treat HC dispatch aliases as five member launches | Rejected. Each fused HC site replaces one low and one inject. `k2_summary.py`. | The actual plan or fusion changes. |
| Retain a handler lambda with reference or implicit-this captures | Rejected. Native compile caught Stream's borrowed copy member; value capture fixed it. `submission-overlay-gates.json`, `LIFETIME.md`. | A new handler passes lifetime/source and native compilation gates. |
| Two indirect calls through prepared callback plus virtual issue | Replaced by a preparation-time callback factory and one concrete per-launch callback. `prepared_submission.hpp`, `LIFETIME.md`. | A changed backend needs a different measured mechanism. |
| Reuse prepared commands after free, explicit invalidation, shutdown or owner address reuse | Rejected before callback invocation. Process-unique owner generations; 13 sanitized invalidation cases. `prepared-invalidation.json`. | Fresh preparation against a valid new owner/buffer set. |
| Allow type-erased compute during capture to execute immediately | Rejected. The base-operation path fails closed; preparation must enqueue nothing. `prepared_invalidation_test.cpp`. | A separately implemented and tested capture path supports erased operations. |
| Call pointer/operation-name parity a full argument proof | Rejected. Current operation fields and geometry are serialized separately; new members must extend the registry. `argument-state-gates.json`, `prepared-equivalence.json`. | Complete argument and launch-sequence gates pass for the new type. |
| Use a placeholder event for eventless work | Rejected: it can report completion before work is safe to retire. Real events remain tracked. `LIFETIME.md`. | A separately qualified segment-completion and failure-containment protocol exists. |
| Move device lambdas or remove local accessors as an assumed host-only edit | Not admitted. Preserve kernel lexical identity, source, SPIR-V names and executable instruction hashes. `kernel-identity.json`. | The unchanged-device proof passes or a separately authorized kernel experiment opens. |
| Treat mock nanoseconds as SYCL issue time or model speed | Rejected. The mock excludes runtime/driver work and Engine dispatch; no device ran. `prepared-host-benchmark.json`. | The coordinator measures the actual W2 plan. |
| Benchmark a real plan with no-op replacement kernels | Not an admitted device issue benchmark. W2 measures actual enqueue_loop_ms; W2c adds profiling family times. `WINDOW.md`. | No revisit under this packet's contract. |
| Interpret a residency read pass as pinned page cache | Rejected. MADV_WILLNEED plus reads are best effort; major faults stay visible and label decode contamination. | A separately approved residency mechanism is qualified. No cache drops or system settings. |
| Reuse inherited packet29 passed booleans as packet35 qualification | Rejected. Fresh source/binary-bound gates and build receipt are mandatory. `inherited-files.json`, `build-receipt.json`. | Never; historical evidence retains its original identity. |
| Use production one-card streaming as though it ran the resident prepared path | Rejected. Streaming remains legacy; CPU audit-prepare-each exercises capture after staging and is labelled accordingly. | A separately tested streaming preparation/invalidation implementation exists. |
