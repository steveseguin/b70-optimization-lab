# Exact FP16 two-card communication prototype

Status: **implemented and CPU-compiled; no GPU execution or speed result**.
This is an isolated operator prototype, not a live vLLM patch. Official target
FP8 weights, FP16 activations/KV and native MTP remain unchanged.

The portable lead is StillDeadcode's uncompressed, out-of-place two-rank sum,
integrated by Radiance. See the pinned [communication source review](../../../../community/1337hero-r9700-qwen38-radiance/validation/2026-09-14-exact-comm-review.md).
The code here is a new Intel implementation of that general approach. It does
not copy AMD assembly, compressed payloads, peer spin or fail-open timeouts.

## What was implemented

The native library exposes dedicated Level Zero input/output allocations,
memory IPC, current SYCL queue submission, finite host event polling, a peer
memory copy directly into output, and a local FP16 sum. Both ranks use fixed
rank order: convert rank-0/rank-1 FP16 inputs to FP32, add, round once to FP16.
No assumption of XCCL equality is made: every output bit must match XCCL,
including signed zero and NaN payload bits. A mismatch is a failed gate that
requires arithmetic diagnosis; it is not permission to weaken the oracle.

The native copy replaces the baseline's local input clone. It still moves the
full FP16 peer payload and launches an addition kernel. The host handshakes
may outweigh any saved collective overhead. This tests a coherent foundation;
there is no predicted speedup and no claim that it is a one-kernel collective.

The current gate uses dedicated input storage populated before timing. It
does **not** solve exporting arbitrary PyTorch suballocations, model producer
allocation ownership, graph capture or concurrent streams. A speed pass would
justify implementing those missing pieces, then repeating the full model gate.
Do not insert a producer-to-mailbox copy into a live integration and claim the
operator benchmark removed that copy: integration must account for all copies.

## Ordering and buffer lifetime

Each rank follows the same sequence for each numbered generation:

1. Complete its local producer on the current in-order queue using a local
   barrier event and bounded host polling.
2. Exchange `READY` with generation, dtype and element count over a private
   Unix socket. No GPU operation waits for a remote event.
3. Copy the peer's immutable input into the local output allocation and wait
   for that local copy's completion.
4. Exchange `COPIED`. Both peer reads have now retired. Only then launch the
   local sum, so even concurrent read/read access to an input allocation is
   unnecessary. No producer can change input while a peer still reads it.
5. Complete the local sum before returning output or allowing input reuse.

Separate Level Zero allocations avoid allocator-slab aliasing. Neither rank
frees its input until both importers close their mappings and exchange a
second close barrier. Export handles are returned only afterward. Linux file
descriptors are transferred through `SCM_RIGHTS`; the native driver FD API must
confirm the assumed IPC handle layout before it is used. Peer UUID and directed
peer-access capability checks precede allocations. Same-device ranks are refused.
The active SYCL/UR adapter must recognize native and imported pointers as device
USM before either is submitted; an unknown interop pointer is a hard refusal.

Any malformed frame, identity mismatch, duplicate phase, peer exit, local
event error or deadline poisons the channel and prevents further submission.
The worker writes a fault receipt and exits without GPU synchronization or
resource teardown that might wait on outstanding driver work. A separate lane
monitor must own the process group and watch kernel faults. Host timeouts
cannot preempt a blocked driver call or a frozen computer; this is not a
hardware-recovery guarantee. There are no restarts or retries in this gate.

The [older B70 peer-spin experiment](../../../qwen36-27b-autoround-int4-b70/esimd_allreduce/README.md)
failed device coherence, imported IPC events and external counter-event waits.
None of those synchronization mechanisms is repeated here.

## Build and CPU verification

`build.sh` performs compilation only; it never discovers or initializes a GPU.
The host build passed with Intel compilers 2026.1 (SYCL ABI 9) and 2025.3
(ABI 8), with fast math and floating-point contraction disabled. Raw build
receipts are `/tmp/mtp-exact-tp2-build-20260914/` and the corresponding
`-sycl8/` directory; [cpu-validation.json](cpu-validation.json) preserves hashes.

Before loading the library, the Python adapter verifies that its required
`libsycl` major equals the one already loaded by PyTorch. It rejects mismatches.
Build with the compiler matching the admitted runtime; do not bring a second
SYCL ABI into a process containing a torch-owned `sycl::queue`.

```bash
python3 -m unittest -v test_protocol.py
bash build.sh
# For the existing host Torch 2.11 / SYCL 8 environment:
EXACT_TP2_CXX=/opt/intel/oneapi/compiler/2025.3/bin/icpx \
EXACT_TP2_BUILD_DIR=/tmp/mtp-exact-tp2-build-20260914-sycl8 bash build.sh
```

Nine CPU tests cover varying-size reuse, missing/closed peers, invalid phase
and identity, FD transfer/lifetime, copy failure and missing peer retirement.
CPU fixture generation and native library loading also passed with XPU still
uninitialized; intentionally mismatched ABI 9 was refused from host Torch 2.11.
These checks establish source/build/protocol evidence, **not GPU correctness**.

## Native gate, only after root-agent admission

The root agent owns exclusive GPU scheduling, runtime identity and the kernel
fault monitor. `gate.py` requires `--admitted-exclusive-gpu-test`; that flag
does not grant permission or acquire ownership. Do not launch alongside the
running model. Use a new output directory and a runtime-matched native build.

The fixed gate checks both ranks at `[1, 5120]`, `[2, 5120]`, `[512, 5120]`
and `[4096, 5120]`: varied finite data, cancellation, signed zeros, subnormals,
overflow, rounding boundaries and NaN/Inf, two changing repeats each. It saves
complete candidate and XCCL binary outputs, input/output hashes and immutable
input checks. Cross-rank output hashes must agree before further submission.

Only after all 14 quality cases at a shape pass does it measure five alternating
ABBA/BAAB blocks of 12 calls. Both arms start from already populated immutable
inputs. Candidate latency includes all host handshakes, device copies and sum
completion; control includes clone, XCCL and completion. Cold JIT has already
occurred during quality checks. No graph overlap or model throughput is inferred.

Operator admission follows the root campaign: at least 5% paired median
improvement at an actually used shape, with positive improvement in all five
alternating blocks. `analyze.py` takes the maximum of both ranks for each
matched arm occurrence before calculating block medians. Qualified shapes may
be routed separately; all other shapes retain XCCL. Even a clean
operator pass cannot promote a model result without exact complete-token,
varied cold-prompt, cached-zero, long-context and determinism qualification.

`run-native.py` freezes source and the CPU-checked library into a read-only
snapshot before one immutable-control-image container is started. It takes the
global stage lock and calls the qualified serve helper's availability check
before granting that container device access. The container has 6 GiB RAM and
8 GiB RAM-plus-swap limits; host memory settings remain unchanged. The controller
watches kernel faults, client failure receipts and a finite overall deadline,
and performs at most one graceful stop of its verified container ID. GPU faults
latch the campaign; ordinary operator/client failures are recorded separately.
It never stops another service or launches a successor. An unconfirmed exit
blocks further work. The standalone output is `communication-native-01` under
the new campaign root. `--check-only` validates files without GPU discovery,
Docker calls, creating the output directory or acquiring the GPU stage lock.

## Source references and limits

- [Level Zero programming guide](https://oneapi-src.github.io/level-zero-spec/level-zero/latest/core/PROG.html): allocation-scoped concurrent-access rules require explicit ordering; ordinary peer access does not imply peer atomics or coherence.
- [Level Zero command lists](https://oneapi-src.github.io/level-zero-spec/level-zero/latest/core/api/apis/command_list.html): ordered copies/events and device-accessible memory requirements. IPC copying is a driver-supported memory operation, not an ad hoc polling load.
- [SYCL USM rules](https://github.khronos.org/SYCL_Reference/iface/usm_basic_concept.html): a kernel's USM allocations and queue must use the same context. Here the kernel reads only its local allocations; the imported peer allocation is used solely as a copy source.
- [PyTorch XPU streams](https://github.com/pytorch/pytorch/blob/v2.11.0/torch/xpu/streams.py): the host queue pointer comes from the existing current stream. The native library does not create another stream or change runtime queue policy.

These references support the chosen APIs and constraints. They do not establish
that this B70 driver passes the candidate's native memory or arithmetic gate.
