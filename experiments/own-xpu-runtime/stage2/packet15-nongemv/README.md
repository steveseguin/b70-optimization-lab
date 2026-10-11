# Stage 2 packet 15 — parallel non-GEMV candidate

**CPU-only preparation, October 11, 2026. SYCL compile/link passes. The
packet1b byte-exact gate FAILS. This candidate is not qualified or integrated
into packet13. No device timing or model speedup is claimed.**

The requested lossless replacement is not complete. The parallel algorithms,
owner-managed launch interface, independent fixtures, guarded device protocol
and timing harness are retained here so the remaining arithmetic problem is
reproducible. Do not replace the oracle, loosen a tolerance, or adopt a changed
output to turn this into a pass.

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

## Arithmetic identity and failing gate

Packet1b's [independent reference](../packet1b/reference.py) supplies expected
bytes. Ordinary norms use `1+w`; recurrence takes BF16 A_log and maps value
head `h` to key head `h/3`. Packet13 instead uses stored gain, F32
`-exp(A_log)` and packed `h%16`. `Shape.flags` explicitly carries unit gain
(bit0), stored decay coefficient (bit1), packed heads (bit2), and FP32 scalar weights
(bit3). Real GGUF convolution, norm and dt weights retain their FP32 bytes;
they are never rounded to BF16 by the loader. Stored-gain FP32 norms and
non-BF16 convolution coefficients have separate fixtures. Packed tests
permute the reference value heads/state and transform the parameter without
changing the expected calculation. No real model weights or prompts were read.

All arithmetic compiles with `-fno-fast-math -ffp-contract=off`; native adds
IEEE denormals. GDN's dot128 is 32 ascending sums of four products, then an
adjacent tree. Other reductions zero-pad odd tails at each stage. No floating
atomics or unspecified SYCL reductions are used. Router error control uses
an integer atomic and a uniform group decision before barriers.

[build-receipt.json](build-receipt.json) is the exact current test count and
source identity. Tests cover synthetic values at real GDN16/48/128, HC4/2560,
512/top10 MoE and QSA24/2/256 shapes, M=1/3/87, small odd shapes, nonzero initial
state, packed layout, ties, NaNs, inactive/error controls, nine-row PLE history,
existing QSA pools, and attention score/probability intermediates. **60 of 72 cases pass** (25,048,064 bytes in passing cases); twelve fail. All
18 CPU-only protocol tests pass. The host
suite runs in two fresh GNU processes and once under the Intel compiler. The
host executable has no accelerator-library dependency.

The failures are genuine: some GDN state/output BF16 values, an 87-row HC mix,
and attention probability/output bytes differ. The independent
[elementary census](math-probe.json) demonstrates C++/torch differences in log,
sqrt and sigmoid. That is supporting localization evidence, **not proof
that all twelve failing fixtures have that one cause**. Native library semantics
remain untested. [The rejected reciprocal experiment](rejected-scalar-reciprocal.patch)
and its [receipt](rejected-scalar-reciprocal.json) preserve a failed attempted
fix. The next task is exact elementary arithmetic/localization, not a new
oracle or relaxed comparison.

The device window checks fixture/source/binary hashes, performs two fresh
owners with two restores/repeats per case, compares every output byte, checks
coverage and safe teardown, and watches a cursor-bounded kernel journal through
a five-second post-exit tail. A fault, lost journal, deadline, bad teardown or
exactness failure latches the window. There is one cooperative SIGTERM, no
hard kill and no retry. Unsafe owners remain alive for the coordinator.
`--check` does only CPU file checks. The exactness command is diagnostic while
the CPU gate fails; timing refuses until both CPU and native exactness pass.

## Reproduce and coordinator commands

CPU-only preparation (build outputs/fixtures stay in this packet's ignored
`build/`, never packet13's live build):

```bash
nice -n 19 env OMP_NUM_THREADS=2 /home/steve/.venvs/vllm-xpu/bin/python -B \
  experiments/own-xpu-runtime/stage2/packet15-nongemv/build.py
```

It returns nonzero on the current exactness failures and preserves the receipt.
`--rebuild-fixtures` regenerates only these deterministic synthetic fixtures;
rebuilding refuses if a packet15 device window or latch is already present.
The roughly 200 MiB ignored tree contains reconstructible fixtures, executable
and compiler output for the coordinator; no scratch directory is retained.

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

**The second command is currently blocked by the CPU exactness failure.**
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

[Closeout](CLOSEOUT.md) records the unqualified state and next exactness work.
