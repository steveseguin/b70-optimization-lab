# Packet47 independent review

Review scope: the standalone kernel, independent CPU reference and CPU tests,
native fixture/timing harness, build provenance, seal, coordinator admission,
event parser, and conditional suite estimate. This review used source reads
and CPU-only Python tests with `nice -n 19 taskset -c 4-15,20-31 python3 -B`.
It did not execute a device program, query a device, read model weights, or
change a sealed packet, service or host setting.

## Arithmetic and bounds

The ordered score kernel preserves the original 256-leaf adjacent tree:
each lane reduces eight consecutive dimensions and the subgroup reduces the
32 resulting values. The ordered PV kernel splits at selected indices that
are multiples of 32. Its lower trees preserve original tail `+0` operations,
and its upper adjacent tree preserves the original global reduction nodes.
Short roots stop at the original depth. The existing denominator division,
BF16 rounding before the gate, deterministic sigmoid, and final BF16 store
remain in the same order. The CPU gates separately compare pre-gate FP32
bytes, preventing BF16 rounding from concealing an arithmetic change.

The split32 oracle and device source agree on fixed selected-index splits,
32-leaf zero-padded lower trees, per-split maxima and exponential sums,
rescaling to the global maximum, upper adjacent reductions and final
division. Its identity is separate from the historical oracle. These are
source/CPU conclusions; E1/E2 must establish compiled-device equality and
fresh-process determinism.

For M=2, the old control is two sequential row-sliced p30 calls. Pointer
offsets cover queries, gates, outputs, selected IDs and score/probability
scratch; each row receives its own causal position. This matches the old
scalar entry point, which rejects a native M=2 shape. The candidate batches
two causally distinct rows. This is an operator comparison, not a claim that
the full engine already executes the candidate batch.

Candidate admission validates selected IDs before dependent KV reads.
The tested invalid position/first-row ID, inactive flag, sticky error and
empty-selection paths preserve attention outputs and the expected error
state. An invalid later row can make the candidate suppress the whole batch
while a sequential old control has already written its valid earlier row.
That malformed-input behavior is outside valid-output equivalence; future
integration must retain explicit fail-closed error handling.

Selection retains the old block-score arithmetic, stable tie rule and
unfinished-block suffix. Qgate retains the old expanded Q6_K lane arithmetic
and final tree32. Its final source uses the production 3380-byte expanded
row stride, including 180 bytes of unused metadata, rather than compacting
rows to the 3200 useful bytes. That source hash matches the device compile
receipt. Neither is claimed as a new optimization. The fixture weights are
generated locally, not read from a model payload.

## Findings resolved during review

- The closed child environment initially omitted the required selector.
  It now pins Level Zero device zero and PCI ordering; native admission
  verifies the selected PCI address against physical DRM card0.
- The evidence parser now requires the full per-class kernel census and
  monotonic nonoverlapping event endpoints, preventing an omitted combine
  or renamed duplicate event from producing an accepted speedup. It also
  requires matching actual/reference hashes.
- Old/new difference evidence is included in the native file hash closure.
- Selection, qgate and attention outputs are poisoned before use so stale
  correct output cannot mask missing writes. Failed byte comparisons retain
  their first mismatch position and bytes. Timing input choice and arm order
  alternate independently; normal attention cases use actual selector IDs.
- The split combine originally replicated a 65-element denominator tree in
  every thread and held two value arrays. It now shares denominator work and
  processes one value dimension at a time. The remaining private value array
  and tile registers still need device timing/compiler evidence; source
  analysis does not establish their spill cost or the 3x/5x bars.

## Provenance, supervision and remaining gates

CPU builds pin their own and inherited sources, verify inputs after building,
and reject accelerator dependencies in host executables. CPU receipts bind
the build receipt, binaries, source identity, four fresh compiler/repeat
processes and losslessly retained raw output bytes. The device compile uses
compiler-generated dependency closure and checks it after compilation. The
seal binds those receipts, source hashes, binaries and raw CPU evidence.
It must be made after the final source and test edits.

The wrapper uses passive ownership checks, bounded memory/journal monitoring,
a single cooperative stop and retained fault evidence. No restart loop or
hard-kill path was found. Coordinator user-unit settings retain a busy child
instead of killing its group. All device admission and ownership remain the
coordinator's responsibility.

The final Python admission/parser suite passed all eight tests in 2.318 s,
including missing/duplicate cases, changed hashes, event census/accounting,
full immutable-buffer byte extents, fault signatures and retained busy-child
behavior. The complete coordinator rehearsal exercises real internal seal,
environment, binary identity and exactness parser logic against all 316
fixture captures. External process, journal and host observations are mocked;
no native device program is invoked.

The suite estimate correctly uses the actual short prompt lengths rather
than treating 4096 capacity as occupied context. Its after values and
throughput sensitivity are explicitly hypothetical. Neither short-context
speed, full-engine logits/tokens, acceptance, nor one-card throughput has
been measured by this packet. Device E1/E2, T1/T2 and subsequent full-engine
qualification remain required before integration or any model-speed claim.
