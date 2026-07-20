# 2026-07-20 Option 4 Phase 1 M1 attention packet blocker

## Numbers first

- **Verdict: BLOCKED before build/gate. Do not claim a Phase 1 pass.**
- GPU execution: none. Logical XPU 2 / PCI `0000:43:00.0` / renderD128
  was verified free and reserved as the safest isolated card, but no device work
  was launched because the mandatory V1 replay packet is absent.
- Protected EAGLE: PID `1710496` remained alive on logical XPU 1 / PCI
  `0000:27:00.0` / renderD131, with FD 4 still bound to renderD131 after the
  audit and immutable-corpus validation. It was not signalled, paused,
  restarted, inspected through a device API, or otherwise disturbed.
- `M1AttentionBoundaryV1` changed-input gate: **not run / 0 qualified of 40**.
- `M1AttentionBoundaryV1` fixed-address replay gate: **not run / 0 qualified
  of 70**.
- All-43 address-specific layer coverage: **0/43 replayable V1 packets**.
- V1 eager/candidate submission-boundary count: **not measurable without the
  missing all-43 packet and transaction**. Phase 0b remains the substrate
  result at one Level Zero boundary and zero host synchronizations for its
  two-operation WQ_B -> fused QNorm/RoPE/KV probe only.
- Endpoint: **deferred**. All four cards are not free, and Phase 1 is not
  component-qualified.
- Phase 2 FFN/MoE boundary: **NO-GO** until Phase 1 has a real packet and passes
  its full gate.

## Why the requested gate cannot run from the existing corpora

The committed build plan explicitly distinguishes the existing M1 MHC corpus
from the new append-only `m1-attention-boundary-v1` packet required to qualify
Phase 1. The existing packet is sufficient only for recurrent MHC input,
output, and alias validation. It does not contain the attention RMSNorm,
WQA/WKV, Q/K/V norm outputs, fused QNorm/RoPE/KV before/after state, QK/LSE,
PV, `wo_a`, rank-local WO_B partial, or fixed weight/address bindings required
by `M1AttentionBoundaryV1`. It also does not contain layer 0's standalone
attention MHC-pre ingress.

A repository, source-tree, `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu`,
and `/mnt/fast-ai/deepseek-v4-corpora` search found no packet named or shaped as
`m1-attention-boundary-v1` / `option4-m1-attention-boundary`. The older
`nospec-w8a16-generic-ring-*capture*` artifacts are diagnostic JSONL files with
tensor shapes and SHA-256 hashes, not tensor payloads. Attention intermediate
captures are layer-0-only. They cannot be replayed, mutated for changed-input
testing, used for fixed-address qualification, or treated as bitwise oracle
packets.

The following planned Phase 1 files are consequently absent as well:

- `validate-option4-boundary-packet.py`;
- `replay-option4-m1-attention-boundary.py`;
- `summarize-option4-m1-attention-gate.py`.

Constructing synthetic Q/K/V, KV cache, indices, or WO outputs around the real
MHC values would not satisfy the committed real captured-tensor gate. Treating
hash-only captures as tensors would be invalid. The audit therefore failed
closed instead of building and reporting an unqualified substitute.

## Existing-corpus validation retained

The protected inputs were read without modification and their validators all
passed:

- real M1 MHC: 692 files, 87 reductions/rank, 85 post/pre boundaries/rank,
  42 aliases, aggregate SHA-256
  `6f8b7b9e7a1c78cc7a2005e2d92d292a80811405725dc43e190526e1be5a59eb`;
- M2 cycle: 688 records, 87 reductions/rank, 85 MHC boundaries/rank, manifest
  SHA-256
  `1015e86b1cf46476dbbd10d1cf0cec92246b8af406149f17b0f2dd62b6dd37cd`;
- sequential M4: 696 records, 87 reductions/rank, 85 MHC boundaries/rank,
  manifest SHA-256
  `8c683206da125533737680501647c689a7f8027a708596f4acc8da7deefb96d6`;
- sequential M8: 696 records, 87 reductions/rank, 85 MHC boundaries/rank,
  manifest SHA-256
  `1354edce1a16cb73143a597a36ab11ab7e10fa61a7afa9763a6273f80b165ebe`.

These remain MHC/reduction regressions. None is V1 attention evidence.

## Exact unblock sequence

1. Wait for EAGLE to release logical XPU 1; do not interrupt it.
2. With all four cards free, make one bounded, default-off K160 TP4 oracle
   capture for both declared context buckets. Record all 43 layer instances,
   including layer 0 standalone MHC-pre, every required intermediate, KV
   bytes/scales and touched/guard addresses, rank-local WO_B partial, weights,
   layouts, aliases, runtime/module identities, and fixed bindings. Create the
   packet append-only beside the existing corpora.
3. Stop the oracle service, then build and run the isolated V1 component gate
   on logical XPU 2 using the Phase 0b raw Level Zero machinery: 40/40 changed
   cases, 70/70 replays including 28 and 58, every layer, full bitwise parity,
   guard checks, injected producer skew, no lazy compilation, zero host syncs,
   and measured eager-versus-V1 boundary counts.
4. Only after that pass, recheck four-card freedom and attempt guarded
   PIECEWISE nesting plus the same-binary nonspec endpoint A/B.

No XPU shared object, vLLM source tree, service, model weights, oneCCL runtime,
held-out pack, or LocalMaxxing state was modified.
