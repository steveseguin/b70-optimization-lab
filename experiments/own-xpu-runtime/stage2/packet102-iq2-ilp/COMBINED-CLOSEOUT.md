# Packet102 combined lookup batching and shared input — closeout

<!-- campaign-closeout -->

## Question and identity

Compose batch2/4 grid issue with shared activations on packet97 IQ2 half-cache,
using `iq3-p49-split32-v1`, without changing FP32 chains. CPU preparation on
steve-b70s, October 18, 2026; linked offline BMG-G31 code and exact CPU fixtures.

## Outcome

All five candidates built and pass exact GNU/Intel byte checks twice.
Shared V8 spills. Shared V4 retains the identical tree; its common epilogue
makes shared-input-only spill-free, but both V4 batched combinations still
spill at 128 GRFs. They fail the preregistered no-spill gate and receive no
micro or engine-screen proposal. No device measurement was made.

## What worked

Batching survives linked code generation: all batch sends precede consumption
without an earlier destination wait. Sharing inputs halves activation loads.
These mechanisms remain separately admitted for diagnostic microbenchmarks.
See the [issue-order proof](evidence/lookup-issue-proof.json).

## What failed or remains uncertain

The per-kernel 256-register property emits `SPV_INTEL_maximum_registers`,
rejected by the installed offline compiler. No unsupported runtime setting
was adopted and no compiler was upgraded. Device speed remains unmeasured.

## Evidence and patches

[Final kernel](p102_expert.hpp), [byte identity](evidence/cpu-byte-identity.json),
[register report](register-report-offline.json),
[V8 source](evidence/attempt1/p102_expert.hpp),
[V4 duplicate epilogue](evidence/attempt2/p102_expert.hpp),
[V4 common epilogue](evidence/attempt3/p102_expert.hpp), and
[unsupported property log](evidence/attempt4-grf-property/compile.log).
Each attempt directory retains its assembly where compilation succeeded.
First V4 engine/byte/startup receipts are under `evidence/first-v4-build`;
restore its kernel from `evidence/attempt2` to rebuild that historical code.
Final combined kernels remain available to CPU gates.

## When to revisit

Require a concrete lower-register composition or a separately qualified
compiler supporting a per-kernel register setting. Keep the standalone
candidates and mandatory 15% device micro gate. No device arm is closed merely
because this CPU preparation has ended.
