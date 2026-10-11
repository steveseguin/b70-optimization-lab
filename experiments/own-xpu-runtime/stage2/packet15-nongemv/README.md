# Stage 2 packet 15 — parallel non-GEMV candidate

**CPU-only correction, October 11, 2026: 72/72 cases pass against the frozen
Packet 4 core under GNU and IntelLLVM, including fresh-process repeats.
18/18 protocol tests pass for each compiler build. SYCL compile/link passes.
Device exactness and timing remain pending; this is not integrated into
Packet 13 and no model speedup is claimed.**

The earlier 60/72 result gated against the superseded Packet 1b Torch path.
Its expected bytes remain a diagnostic column; they do not define runtime v1.
The arithmetic authority itself is unchanged.

## Why recurrence takes a second

Packet13's `main.cpp::enqueue` sends its non-GEMV sites to
[packet4/kernels.cpp](../packet4/kernels.cpp). That adapter launches
`single_task(integrated::evaluate)`: **one GPU work-item for the entire site**.
[The interpreter](../packet4/kernels.hpp) widens and copies every input and
output to an FP32 scratch pool. [Core::run](../packet4/core.hpp) then loops over
48 heads, 128 value rows per head, and 128 key elements per row. Each dot
allocates products, four-product partials and cloned reduction trees; state is
copied and rounded serially. BF16 conversions are scalar integer bit operations
inside these loops, not a hardware-wide recurrence kernel.

The [live-prefix snapshot](before-snapshot.json) contains 1,080 completed
recurrence sites averaging **1,048.596 ms device time with one submission per
site**. This is decisive evidence for scalar execution, not a per-element
launch storm. The file was growing; these are prefix observations, not final
run totals. QSA costs grow with the position, so different snapshots have
different averages. The first token includes compilation/startup and is not a
steady-state speed observation.

Packet13 also waits in `finish()` after every site, reads `error` to the host
after every site, and reads router IDs for one-card weight streaming. Those
round trips add wall time; they do not explain the ~1 s *device* recurrence.
The supplied ~440 submissions/layer should not be attributed to recurrence:
the observed recurrence has exactly one physical submission.

## Kernels and launch plan

Original lab code: [kernels.hpp](kernels.hpp), [native.cpp](native.cpp),
[native.hpp](native.hpp). CPU mock and native use the same group body and
explicit adjacent-pair reductions. Native groups distribute work with 128
work-items; recurrence uses 32. Every submitted operation uses the Stage1
[owner](../../stage1/packet3-prep/README.md), existing arena handles and explicit
event dependencies. No internal allocation, wait, copy, host route selection
or readback occurs in `ng::submit`.

| Existing site | Before: ms/site in the captured prefix | New work | Launches |
| --- | ---: | --- | ---: |
| `gdn.recurrence` | 1,048.596 | 6,144 groups run independent head/value rows; 32 lanes each calculate four ascending products then the fixed tree. All T rows scan inside the kernel. Output uses updated FP32 state, then state commits BF16 before the next row. | 1 |
| `gdn.conv` | 49.296 | Channels run in parallel; chronological four-tap accumulation and history shift scan all T rows inside each work-item. Dilation1 and separately tested PLE dilation3 casts. | 1 |
| `hc.a.norm`, `hc.f.norm` | 14.515, 14.522 | A group per stream computes the exact tree then distributes gain/output stores. | 1 each |
| `hc.*.mix` | `hc.a.mix`: 7.919 | Output columns run in parallel; stream accumulation remains 0,1,2,3, then divide4/BF16. | 1 each |
| `attn.combine`, `ffn.combine` | 10.838, 10.833 | Materialize BF16 combined residual and compute the next norm in the same group/launch, keeping its BF16 boundary. | 1 each, including next norm |
| `route` + `gather` | 11.540 + 17.416 | Softmax, stable rank/top-k, selected renormalization, both expert descriptors and repeated input gather share a launch. Reject nonfinite router inputs with a sticky error. | 1 total |
| MoE combine | separate ordered mixture in packet13 | Columns run in parallel; selected experts accumulate in logical order, routed/shared contributions round separately, then add/BF16. | 1 |
| `gdn.gated` | 11.764 | Head RMS tree, ordinary gain, sigmoid gate and BF16 output fuse. | 1 |
| QSA prepare | serial interpreter | Parallel head norm, BF16 norm boundary, split-half RoPE with BF16 trig, and gate extraction. | 1 |
| `qsa.pool` | 67.048 | Append KV/raw keys and compute only newly completed chronological pools. Pool reads current keys directly, so there is no cross-group append/read race. Old complete pools remain untouched. | 1 |
| QSA selection | serial interpreter | Blocks compute fixed-tree index dots; head-order score accumulation and stable ranks produce selected-order IDs and the causal tail. | 1 |
| `qsa.attention` | 114.299 | Score trees, max-subtracted softmax, selected-order PV trees and BF16-before-sigmoid gate. Launch only admitted score slots, not all padded slots. | 3 |
| HC activation / FFN SiLU-product | serial interpreter | Parallel elementwise work; preserve divide4-before-SiLU and BF16 output. | 1 each |

For a prompt, each attention row uses only its own completed pools and causal
selected IDs even though append/pool prepare the whole admitted chunk. The
prompt PV path favors a clear fixed tree over speed. Maximum admitted chunk
is 87, context capacity is 4,096, budget is at most 2,048; widening these bounds
requires a fresh memory/shape check. Actual attention KV and recurrent state
stay BF16. Architectural QSA pooling does not change KV precision.

A single layer cannot fuse through intervening GEMVs without changing their
interfaces. The provided synthetic census enqueues **14 GDN / 17 QSA launches**
with no intermediate host waits, then waits once. This includes preparation of
the following HC norm, and explicit routed/shared activation kernels (a GEMV
implementation that already fuses activation must omit those). It is a
preregistered non-GEMV sequence with independently prepared projection inputs,
**not a connected full layer**. It excludes PLE, final sampler/head, GEMVs,
weight streaming and graph replay. Packet13's caller-side waits/error reads
and host-routed one-card streaming remain there until separately integrated.

Planning estimate, **not measured**: roughly **0.1–0.6 ms per GDN layer at M=1**,
and **0.2–1.5 ms per short-context QSA layer**. This assumes microsecond-scale
launches, parallel 3 MiB recurrent-state traffic and short attention. Local
barriers, occupancy, JIT and elementary-library cost could invalidate it.
The goal of a few ms for the whole token is not established by these ranges;
long context and full-step capture still need work. No predicted point belongs
in a benchmark, package or performance curve.

## Arithmetic identity v1 and the corrected gate

The authority is the unchanged [Packet 4 core](../packet4/core.hpp), as bound
by [its interpreter](../packet4/kernels.hpp). The
[arithmetic decision](../../../../notes/2026-10-11-iq3-arithmetic-authority-decision.md)
and [rebased runtime oracle](../../../qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/README.md)
explain why: Packet 1b uses Torch vector-library elementary functions and
`rsqrt`, while runtime v1 uses scalar FP32 `std::exp`, `std::log`, `std::sqrt`,
`1.f / std::sqrt(...)`, and explicit reduction trees. The rebased oracle at
`9ee12b3527` and Packet 13 CPU mock at `1c9af40c1e` match all 48 layer hashes
([first-token evidence](../../../../notes/2026-10-11-first-token-correctness.md)).
Changing the candidate to match the pre-rebase Python path would change this
identity. This correction changes which existing authority the test uses,
not the authority's equations or tolerances.

[reference.hpp](reference.hpp) is a thin adapter around `integrated::Core`.
It calls `Core::run()` once per synthetic row, retaining convolution/recurrent
state between rows and resetting the interpreter scratch. Compound sites call
the corresponding core operations in order. Attention final output comes
from `Core::run`; the exposed score/probability buffers use `Core::dot/tree`
and the same core expressions, since the interpreter does not expose them.
No expected arithmetic calls Packet 15's parallel group body.

All 72 original `.fixture` files retain their original inputs **and** Packet
1b-derived expected bytes. `.fixture.core` and `.fixture.core.icpx` separately
store GNU and IntelLLVM Packet 4 expected bytes. `build.py` regenerates both
with the core, hashes every file, then checks each compiler's fresh core and
candidate against those bytes. Reports keep `packet4_passed`,
`packet1b_diagnostic_passed`, `packet1b_differing_bytes`, and
`packet4_core_vs_gnu_differing_bytes` for every case. A failed gate reports the
first differing slot, byte and element; no tolerance is used.

`Shape.flags` preserves all original fixture semantics: unit-offset gain
(bit 0), stored FP32 decay coefficient (bit 1), packed heads (bit 2), and
FP32 scalar weights (bit 3). The adapter passes stored gains directly for
runtime cases and transforms unit-offset fixtures for core sites that require
stored gain. It passes stored `-exp(A_log)` without exponentiating it again;
legacy A_log fixtures transform it once in FP32. Runtime recurrence uses
`h%16`, while the separate legacy-layout fixtures retain `h/3`. FP32 norm,
convolution and dt weights never round to BF16. No weights or prompts from the
real model were read.

The candidate expressions follow the core, including:

- sigmoid `1.f / (1.f + std::exp(-x))` and SiLU `x * sigmoid(x)`;
- RMS inverse `1.f / std::sqrt(sum / float(width) + 1e-6f)`;
- GDN `(q / qn) / std::sqrt(float(d))`, ordinary `k / kn`,
  `gate < 20.f ? std::log(1.f + std::exp(gate)) : gate`, and
  `std::exp(stored_a * sp)`;
- attention **K times Q**, then division by `std::sqrt(float(ad))`,
  max-subtracted exp, adjacent-tree denominator and ordinary division;
- BF16 before rotary and on trig values; PLE convolution BF16 **before**
  SiLU; GDN state BF16 **after** the updated-state output dot; attention PV
  BF16 before the sigmoid gate; separate routed/shared BF16 boundaries.

All builds retain `-fno-fast-math -ffp-contract=off`; native adds IEEE denormals.
GDN dot128 uses 32 ascending four-product sums, then the adjacent tree.
Other trees zero-pad odd tails at each level. The changes align operand order,
FP32 literals, square-root division and max selection; the already-correct
rounding boundaries are preserved. **Neither Packet 4 header was edited.**

[build-receipt.json](build-receipt.json) records **72/72** core matches and
**79,551,248 compared bytes per run**, in two fresh GNU and two fresh IntelLLVM
processes. The same **12/72** cases still differ from the old Torch diagnostic:
GDN source, packed and runtime-FP32 variants at M=1/3/87; HC mix at M=87;
and attention at M=3/87. All **18/18** CPU protocol tests pass for each build
(the Python protocol tests themselves are compiler-independent).
Remaining candidate-versus-core failing cases: **none**.

GNU links glibc scalar libm; IntelLLVM links Intel scalar libm. Their core
results differ in **1 byte** for attention M=3 and **26 bytes** for M=87,
so cross-compiler CPU bit identity is **not** claimed. Both candidates match
their own compiled core exactly. [math-probe.json](math-probe.json) and the
[rejected reciprocal experiment](rejected-scalar-reciprocal.patch) remain
historical diagnostics; matching Torch is no longer a gate.

### Decisive device gate (prepared, not run)

CPU libm versus device libm may differ for exp/log (and other elementary
functions). Matching source expressions is necessary, but the on-device byte
comparison decides whether the parallel lowering matches the scalar core.
The card-3 window now runs the unchanged Packet 4 core in a `single_task`
with the **same SYCL compiler, card and input bytes**, then restores every
input and runs the candidate twice. Each row is a separate bounded reference
submission sharing a 256 MiB scratch allocation; reference work is excluded
from candidate timing. It records device-core versus GNU-CPU differences as
diagnostics, and gates every candidate output byte against **device core**.

The window uses two fresh owners. Device-core output bytes are retained as
`ownerN/*.fixture.core`; their SHA256 hashes must also match across owners.
Timing admission rechecks their hashes and full 72-case core coverage, in
addition to candidate coverage and safe teardown. The same controls reject
inactive/error writes and unexpected core failures. A 900-second owner deadline
allows the serial reference census; the per-event deadline stays 30 seconds.
These are bounds, not measured durations. The existing journal fault watch,
five-second post-exit tail, cooperative SIGTERM, no hard kill and no retry
remain. `--check` performs CPU file checks only. Native timing remains blocked
until the native exactness proof passes.

## Reproduce and coordinator commands

CPU-only preparation (build outputs/fixtures stay in this packet's ignored
`build/`, never packet13's live build):

```bash
nice -n 19 env OMP_NUM_THREADS=2 /home/steve/.venvs/vllm-xpu/bin/python -B \
  experiments/own-xpu-runtime/stage2/packet15-nongemv/build.py
```

It returns nonzero on any candidate/core or repeat failure and preserves the receipt.
`--rebuild-fixtures` regenerates only these deterministic synthetic fixtures;
rebuilding refuses if a packet15 device window or latch is already present.
The ignored build tree contains reconstructible fixtures, both compilers'
core outputs, executables and compiler output for the coordinator; no scratch directory is retained.

After separate coordinator card/host admission, the two card-3 commands are:

```bash
nice -n 19 env OMP_NUM_THREADS=2 /home/steve/.venvs/vllm-xpu/bin/python -B \
  experiments/own-xpu-runtime/stage2/packet15-nongemv/device_window.py \
  --authorized-device-window --card 3 --mode exactness \
  --output experiments/own-xpu-runtime/stage2/packet15-nongemv/build/card3-exact-a
```

```bash
nice -n 19 env OMP_NUM_THREADS=2 /home/steve/.venvs/vllm-xpu/bin/python -B \
  experiments/own-xpu-runtime/stage2/packet15-nongemv/device_window.py \
  --authorized-device-window --card 3 --mode timing \
  --exactness experiments/own-xpu-runtime/stage2/packet15-nongemv/build/card3-exact-a/window.json \
  --output experiments/own-xpu-runtime/stage2/packet15-nongemv/build/card3-timing-a
```

**The second command remains blocked until native exactness passes.**
Timing would report raw per-op rows plus measured GDN/QSA sequence device and
wall ms for M=1/87. Each of two fresh owners has one untimed-from-summary initial
iteration and five retained samples; no state is reused between iterations.
These synthetic kernel timings never satisfy the realistic model benchmark.

## Buffer interface

All slots below are arena allocations. Activations/state use two-byte BF16;
scalar weights use BF16 or F32 as selected by flag bit3. `P` is F32,
IDs/routes/control are I32. Slot15 is `[position,active,error]`. Unused slots
still bind a four-byte allocation. `required_bytes` validates every extent
before submission. Inputs and outputs must be disjoint except explicitly owned
working cache/state; committing model state is the caller's responsibility.
All state here belongs in the transaction arena specified by
[One captured decode transaction](../../DESIGN.md#one-captured-decode-transaction).

| Op | Input slots | Output slots |
| --- | --- | --- |
| conv | 0 X[T,C], 1 history[C,3*dilation], 2 W[C,4] | 3 Y[T,C], 4 history |
| gdn | 0 QKV[T,10240], 1 a[T,48], 2 b, 3 A_log or stored F32 A, 4 dt, 5 state[48,128,128] | 6 Y[T,48,128], 7 final BF16 state |
| norm | 0 X[T,heads,W], 1 gain[heads,W] | 2 normalized |
| activation | 0 gate; 1 up when extra=1 | 2 activated (extra=0 is HC divide4) |
| mix | 0 normalized[T,4,W], 1 gates | 2 mixed[T,W] |
| combine_norm | 0 streams, 1 branch, 2 injection[T,4], 3 next gain | 4 combined BF16, 5 next norm |
| route_gather | 0 logits[T,experts], 1 X[T,2560] | 2 IDs, 3 P, 4 gathered X[T,top,2560], 5 gate/up routes, 6 down routes |
| moe_combine | 0 down[T,top,W], 1 P, 2 shared[T,W], 3 shared gate[T] | 4 combined |
| gated_norm | 0 Y[T,48,128], 1 z, 2 gain[128] | 3 gated |
| prepare | 0 Q/gate[T,24,512], 1 K[T,2,256], 2 IQ[T,4,128], 3/4/5 gains | 6 Q, 7 gate, 8 K, 9 IQ |
| pool | 0 K, 1 V, 2 raw, 3 pool gain; 4/5/6/7 working prior caches | 4 K cache, 5 V cache, 6 raw cache, 7 complete pooled keys |
| select | 0 IQ, 1 pooled keys | 2 IDs[T,budget+3] |
| attention score / softmax / value | 0 Q, 1 gate, 2 K cache, 3 V cache, 4 IDs | 6 F32 scores, 7 F32 probabilities, 5 gated BF16 output respectively |

[Closeout](CLOSEOUT.md) records this authority correction and the remaining device gate.
