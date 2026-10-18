# Packet102 combined lookup batching + shared input closeout

<!-- optimization-closeout-v1 -->

Question and identity: compose batch2/4 grid issue with shared activations on
packet97 IQ2 half-cache (`iq3-p49-split32-v1`), without changing FP32 chains.

Outcome: all candidates built and pass exact GNU/Intel byte checks twice.
Shared V8 spills. Shared V4 retains the identical tree; its common epilogue
makes shared-input-only spill-free, but both V4 batched combinations still
spill at 128 GRFs. They fail the preregistered no-spill gate and receive no
micro or engine-screen proposal. No device measurement was made.

Useful mechanism: batching survives linked code generation; all batch sends
precede the first consumption. Sharing inputs halves activation loads. These
mechanisms remain separately admitted for diagnostic microbenchmarks.

Failure/uncertainty: a per-kernel 256-register property emits
`SPV_INTEL_maximum_registers`, rejected by the installed offline compiler.
No unsupported runtime setting was adopted and no compiler was upgraded.

Retained evidence: `evidence/attempt1` (V8), `attempt2` (V4 duplicate epilogue),
`attempt3` (V4 common epilogue), `attempt4-grf-property` (unsupported property),
`register-report-offline.json`, `evidence/cpu-byte-identity.json`, and the final
`p102_expert.hpp`. First V4 engine/byte/startup receipts are retained under
`evidence/first-v4-build`; restore its kernel from `evidence/attempt2` to rebuild
that historical code. Final combined kernels remain available to CPU gates.

Revisit only with a concrete lower-register composition or a separately
qualified compiler that supports a per-kernel register setting. Keep the
current standalone candidates and mandatory 15% device micro gate.
