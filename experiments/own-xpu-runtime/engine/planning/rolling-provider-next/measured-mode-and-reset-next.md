# Next: measured rolling mode and persistent cold requests

Design only, 2026-10-25. No implementation or qualification is claimed here.
The current rolling proof uses binary `8e03d3cd67fc99c7db4408cb9c2e6abb158806f142df16292ece37083e706231` and remains frozen while it runs. This note does not change its source, controller, evidence rules, or publication status.

The smallest useful next step is two separately admitted capabilities: omit expensive diagnostic readbacks while retaining the checked execution protocol, and reset a quiescent ring request without replacing any process or device allocation. Neither is currently supported by the admitted rolling driver. Its 32-token limit and mandatory diagnostic checks must not be silently relaxed.

## Measured controls

Use an explicit new native policy, for example `--pipeline-ring-check-policy measured`, admitted only with the existing ring/live/partition/pending-provider capabilities. Keep the present policy as the default qualification policy. Do not reinterpret the absence of existing verification flags as authorization to bypass the present mandatory checks. Reject contradictory combinations before device initialization. The new controller must carry the policy in its plan, source closure, request identity and result.

| Operation | Qualification policy | Proposed measured policy |
| --- | --- | --- |
| Target snapshot capture and suffix restore | Complete checked copies and host/bank/shared-output restoration | Identical |
| Target restore full image/allocation readbacks | Required | Omitted, explicitly counted as unverified |
| Canonical provider advance, private capture, recursive compute and restore | Existing implementation | Identical |
| Provider restore full canonical-device and pinned byte readback | Required | Omitted, explicitly counted as unverified |
| Complete provider survival capture before/after target ABORT | Required | Omitted; no survival proof is asserted for that abort |
| Allocation census, disjoint ownership, extent and descriptor checks | Required | Required |
| Row/parent/request/epoch/commit/serial checks and final-owner lease | Required | Required |
| Ordered queue completion, host restoration equality and sticky-error checks | Required | Required |
| Final target/draft state comparison in the bounded parity gate | Required | Required, outside timed decoding |

Do not add a third arithmetic path. Existing switches already reach the costly target and recursive verification branches: `CheckpointRing::restore` in [checkpoint_ring.hpp](../../src/pipeline/ring/checkpoint_ring.hpp), and `DraftRuntime::recursive_restore(bool verify)` in [draft_runtime_extension.inc](../../src/pipeline/recursive_provider/draft_runtime_extension.inc). The latter still compares complete restored host/target metadata when byte verification is false. The extra before/after survival reads are in `Dispatcher`'s ABORT branch and [pending_survival.inc](../../src/pipeline/recursive_provider/pending_survival.inc).

The narrow source changes would be parser admission in `src/gsq-rco-iq3s/dense-packed-block/engine/build/source/main.cpp`, policy plumbing and accounting in [dispatcher.hpp](../../src/pipeline/ring/dispatcher.hpp), and new explicit attestation semantics. Do not change the existing v4/v5/v6 proof schemas. A measured attestation must distinguish:

- Actual target captures/restores/releases from full target byte checks.
- Actual recursive captures/restores from full recursive byte checks.
- Provider borrows by pending depth from provider-survival receipts/checks.
- Mandatory host/identity checks from optional complete byte verification.

In particular, the present invariant `survival_records == ring.abort_count` cannot remain a claim in measured mode. Report actual aborts and zero omitted-survival checks separately, with the selected policy. Preserve the current equality under qualification policy. Do not report `all_restores_byte_verified` as true merely because verification was disabled; expose enabled, required and performed counters explicitly.

Keep the current full command/provenance witness for the first measured parity gate. Its JSON serialization, flushes and trace costs remain part of that measured configuration. A later compact trace policy is a separate change requiring lossless reconstruction or narrower claims; it is not part of this minimum patch. Final state dumps and finalization are outside the decode interval, while every operation between first decoded input and last target output remains inside it.

The retained diagnostic medians (canonical 2.045 ms, recursive 2.007 ms, capture 0.465 ms, restore 10.051 ms) include verification work, particularly full allocation readbacks in restore. They do not estimate production restore cost. Keep the current per-allocation copy implementation for the first parity gate. Combining copies with checked descriptors is a later measured optimization, not a prerequisite or assumed gain.

## Persistent ring RESET: proposed wire and boundary

Add a distinct `--pipeline-ring-persistent-requests` opt-in. Do not make the existing wavefront-only persistent flag automatically admit ring requests. Reuse op 11, currently refused by ring admission, with all ordinary payload fields zero and the ordinary next global wire sequence. Stage/final-stage identity checks remain mandatory. No RESET on a fault, poisoned owner, sticky error, incomplete cancellation, unresolved target row, active snapshot, queued callback, active recursive branch or unmatched provider/final-parent lease.

The controller must first reach a complete request boundary on every owner. The current rolling qualifier only proves matched full-cap termination; early EOS and cancellation must remain refused for this reset capability until separately qualified. The provider must have processed exactly the permitted nonterminal true pairs, with its canonical position equal to `max(0, target_position - 1)`, before any reset mutates state.

Keep reset metadata at the ORIGINAL native output directory, named by the actual global wire sequence. A new bounded ring-specific descriptor should contain exactly these admitted values:

- Schema `ownrt.ring-reset-request.v1`.
- Current and next epoch; next must equal current plus one, without uint64 wrap.
- Current request digest and next request digest.
- Stage ID and expected global wire sequence.
- Fresh absolute destination under that owner's original output directory.
- Unchanged oracle string, normally empty; do not allow reset to introduce an oracle.

The next request digest binds the immutable new prompt/config identity shared by all owners; each stage's output destination differs. Derive the new initial prefix using the existing domain-separated `ring_request_prefix(next_request, next_epoch)`, not a controller-supplied arbitrary prefix. The descriptor is consumed once through a bounded regular-file FD, duplicate keys refused, stable file identity checked, symlink and dangling-ancestor destinations refused. Reuse the checked I/O/path approach in [request_reset.hpp](../../src/pipeline/request_reset.hpp), then pass admitted values directly into the existing owner-zero implementation. Never validate one pathname and let legacy reset reopen it.

Reply remains an ordinary op-11 ACK with zero token/bytes, but a new `ring-reset.json` receipt in the destination binds previous/next epoch and request digest, stage ID, global sequence, original physical allocation inventory hash, target/provider position zero, both context extents, empty target pending/slots, provider idle, and counter/trace reset status. The controller validates every receipt before issuing any new ROW. A failed reset is terminal for the run; no retry or process cycle.

Global socket sequences never reset. Request-local row IDs, accepted-prefix state, provider serial and counters do reset under the new epoch/request identity. The controller creates a fresh coordinator seeded from every actual `Stage.sequence`, not from zero. Old replies, old final records, old proposal batches and old source publications must fail context validation. Preserve persistent process IDs, shared-file identities, immutable model/quant/profile identities and all device allocation IDs across the boundary.

## Reuse points and required state inventory

[StageRing::reset](../../src/pipeline/ring/stage_ring.hpp) already checks a quiescent physical/committed boundary, epoch increment and sticky health; it clears request-local row/commit state and counters while retaining wire sequence. [EngineBackend::reset](../../src/pipeline/ring/engine_backend.hpp) already invokes an optional owner-reset callback followed by `CheckpointRing::reset_after_owner_zero()`. The dispatcher currently does not bind that callback or expose native RESET. Use those hooks instead of duplicating the executor.

The owner-zero callback should call the narrowly factored [legacy request_reset](../../src/stage2/packet194-expert-diet-engine/request_reset.hpp) with already admitted values and a quiescent Candidate. This resets physical target banks, recurrent/KV tails, scratch, lookup/history state and canonical provider buffers. It preserves immutable weights and physical allocations. Its `fp32_sources` and `fp32_extents` are logical cache contents and are cleared without allocating replacement backing buffers. Confirm this against the real allocation census after the first new request, not only at reset ACK.

The ring callback must additionally handle the following inventory explicitly:

1. **Target descriptors and both context banks.** Generic owner-zero clears ring image/capture/restore allocations. `CheckpointRing::reset_after_owner_zero()` must then reprepare and reupload both slots' checked copy descriptors, restore both extents to 32, clear saved metadata/shared-output bytes and counters, and verify the original inventory. Do not skip zeroing arbitrary runtime-overhead allocations or reuse zeroed descriptor tables.
2. **Canonical provider.** Existing `DraftRuntime::reset_request` zeros canonical device buffers and both pinned publication/staging buffers, clears publication callbacks, and resets basic position. Its persistent-only host branch must be explicitly applied to the new ring capability: pending head/confirmed fields, queued probe markers, owned reverse bytes, and context extent 32. Admission must reject callbacks before calling a drain that could execute them. Rebind existing prepared attention commands after the extent reset without reallocating buffers.
3. **Recursive private provider state.** Existing `reset_request` does not reset `recursive_host`, `recursive_target`, `recursive_class`, per-row `pinned_before`, or recursive capture/restore/verification counters. Clear these explicitly at an already idle boundary. Zero the existing private image through owner-zero, retain its ID and exact census, keep `recursive_active=false`, and clear private saved metadata. Do not call `prepare_recursive_depth2()` again: it allocates storage and is initialization-only. Reset stale timing/queued host fields to a defined cold value so full-state receipts are deterministic.
4. **Provider sequence.** Recreate the ring-specific `recursive_provider_next::Sequence` with the new context, position 1, serial zero and empty prior seed/result. This is not the older wavefront `live_draft::Sequence`. Preserve the outer global wire watermark and ensure first op27 after reset cannot accept a stale prior-epoch record.
5. **Dispatcher state.** Update context and the request identity used by native sidecars/attestations. Require `provider_at_capture` empty, clear its storage, clear pending-depth histogram and all survival/draft/target trace counters. Seal/close old streams and reopen under the fresh request destination. Re-emit request identity metadata; copy only immutable layout data whose hash remains valid. Do not overwrite the previous request's evidence.
6. **Final publication and peer ownership.** Clear shared command/publication data only after all owner sockets and leases are drained. Preserve each shared file's inode, size and mapping. Keep the held readonly final-peer FD and inode checks, but invalidate the old final record marker and clear any cached request-local event identity. The first new op27 must bind a new-epoch parent record. Do not reopen a replacement path as an implicit recovery.
7. **Counters and evidence.** Clear native per-request timing/submission/cache-preparation counters after descriptor reconstruction and final boundary readbacks. Preserve lifetime safety identity separately. Report reset wall time/bytes and request IDs outside the decode interval. Optional before-reset raw dumps remain off during a 12-prompt benchmark; perform full dumps only in the dedicated reset qualification or at the requested final boundary.

The existing wavefront `persistent_reset` combines different ledger and provider-sequence types; invoking it directly would be incorrect. Factor only shared validated owner-zero/counter routines where useful. The ring-specific lifecycle and attestation stay explicit.

## Qualification and rollout order

1. Finish and archive the current rolling proof. It supplies no authority to omit checks or reset ring state.
2. CPU state-machine/Host tests for ring RESET: global sequence continuity, epoch wrap refusal, stale batch/final record rejection, no reset with pending work/fault, bounded metadata refusals, both context banks and checked descriptor reconstruction, unchanged physical allocation census, recursive private/pinned/host/Sequence cold state. Include two identical requests and a second prompt with a different length that crosses an extent boundary.
3. One persistent multi-owner correctness run, qualification policy throughout: two identical cold prompts, full target/draft dumps after each, compared with the accepted sequential reference and each other. A second request must demonstrably start at position zero with no cached prompt state. All owners stay loaded; no retries or replacement servers.
4. A separately admitted bounded measured-policy parity run against the checked rolling result: same model, topology, prompt, cap, dispatch, output and final full state. Optional readback counters must show omission honestly; mandatory copies and host checks remain. Compare observed schedules/proposal provenance too, because reduced diagnostic latency can change speculative issuance without changing target truth.
5. Only after these gates, use one persistent owner set for the matched 12-prompt cold suite at 512-token caps. Remove the controller's present 32-token guard only in the new admitted planner, retaining context/position and signed wire bounds. Include exact timing boundaries, per-prompt outputs, reset receipts, verification/trace policy and source/build/model identity. The existing two-card result and diagnostic quad result are not interchangeable baselines.

These gates establish honest throughput measurements; they do not promise a speedup. The final-owner lease and stage-0 ordered provider/target work remain real serialization costs. Optimize or redistribute them only after the measured component costs identify the next bottleneck.
