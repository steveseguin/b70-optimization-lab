# Packet 3 preparation — resource ownership, CPU tests and compile only

2026-10-10. This is independently written C++20 preparation for
[packet 3](../../STAGE1-PLAN.md), not a passed native packet or model runtime.
The owner's task authorizes host compilation and mock tests only. **Native
execution remains unauthorized.** The four-card host halt is unchanged.

## What exists

- [Device and Arena](src/owner.hpp), [implementation](src/owner.cpp): one
  owner per selected card, no copyable owners, named allocation rows, memory
  totals, explicit category/lifetime checks and graph buffer leases.
- [SYCL backend](src/sycl_device.cpp): one in-order queue, constructed from
  an explicit Level Zero context restricted to the selected device. Native
  context ownership stays here until all SYCL wrappers are released. A
  second owner for the same card is refused. Missing Level Zero fails closed;
  there is no implicit multi-card or alternative-backend fallback.
- `CopyEngine`: at most two pending copies, each at most 128 MiB. Explicit
  caller dependencies and the preceding submission are retained. Backpressure
  refuses another copy until the caller completes existing work. Extents,
  freed buffers, aliases and handles from another owner are checked. The
  ledger admits at most 4,096 submissions per bounded owner session.
- [MockDevice](src/mock_device.hpp) executes only ordinary host memory copies
  when the test explicitly completes them. Its interface is the same one used
  by the SYCL backend; host targets contain no SYCL headers or device library.
- [Smoke](src/smoke.cpp): enumeration, three 4 KiB allocations (one device,
  two pinned), two changed-pattern round trips, census, shutdown and receipt.
  Only its **MockDevice build** was run.

The original code follows this lane's [ownership design](../../DESIGN.md).
The 128 MiB limit comes from the lab's
[copy-mapping diagnosis](../../../../docs/host-stability-and-fault-diagnosis.md#a-second-machine-gpu-faults-that-came-from-a-container-memory-limit)
(described in the two-card memory-limit section); it is not a measured native
limit for this implementation. SYCL/Level Zero interop is an Intel platform
API dependency. No external runtime code was copied or linked.

| Census category | Planned lifetime | Shutdown group |
| --- | --- | --- |
| weights | process | weights |
| KV, recurrent-state | request | KV/state |
| workspace | transaction | workspace |
| graph-static | graph | workspace, after graph destruction |
| output-ring | request | workspace |
| pinned-copy-slab, loader-staging | transfer | backing, after weights |
| host-shadow | process | backing, after weights |
| runtime-overhead | process | workspace |

Every allocation also names device, host-pinned or host-shadow memory.
`host-shadow` means an explicit ordinary-host allocation. Driver-created
shadows and library pools are reported **unknown**, not zero; native admission
must compare the census with host memory observations. There are no invisible
library pools in this small smoke, but driver backing has not been measured.
No alias allocator, model weights, KV arithmetic, graph capture, replay,
collectives, worker pool, separate compute streams, peer copy or overlap is
implemented. Graph registrations hold destruction callbacks and buffer leases
to test ownership; they do not claim working SYCL graph capture. Transaction
scratch and transfer slabs cannot be captured; persistent capture workspace
must be registered as graph-static. Public operations are single-controller
thread operations; producer threads must be joined before invoking shutdown.

## Shutdown and refusal

Quiesce rejects new allocations, copies and graph registrations. Drain waits
every tracked event under one deadline and synchronizes the owning queue.
Only then does shutdown release graphs, workspace/static/output buffers,
KV/recurrent state, weights and host backing. A final queue marker is submitted
after frees and waited to completion; events, queue, SYCL context and native
Level Zero context are released last. There is no sleep-as-idle-proof.

An incomplete drain returns status `refused`, code 75 and `safe_to_exit=false`;
buffers stay owned. Completion can then be supplied by the mock and shutdown
called again. A pending final marker retains events/queue/context. Native
backend errors latch refusal and forbid automatic cleanup retries. The smoke
writes the refusal and holds ownership for its supervisor rather than exiting
with work in flight. The destructor also drains cooperatively; if that cannot
establish safety it holds rather than calling `_Exit`, terminate or a kill.
The event deadline does not bound a driver call that itself blocks: queue
synchronization, free and context destruction still need native qualification.

Receipt code 0 requires zero live arena bytes, no in-flight events, a completed
idle marker and ordered context release. Code 1 denotes a failed smoke even
when cleanup succeeds. The [JSON schema](tests/teardown.schema.json) covers
process-local teardown; a clean external kernel postflight is a separate gate.
The [stability guide](../../../../docs/host-stability-and-fault-diagnosis.md)
distinguishes GuC/interrupt hard lockups from process-teardown engine faults.
This preparation proves neither fault class fixed and runs neither probe.

## Builds and tests

[CMake](CMakeLists.txt) pins the recorded icpx 2026.0.0 toolchain and libze-dev
1.28.2 headers from the [toolchain inventory](../../data/toolchain-20261010.json).
The header's Level Zero **API** version has its own numbering; package 1.28.2
does not mean API 1.28. Native compile uses C++20 and `-fsycl`. Host-only mode
uses C++20 without `-fsycl`, SYCL device targets or device-library linkage.
CMake compiler checks create static archives and never run a device probe.

The [build receipt](build-receipt.json) retains compiler/package versions,
exact configure/build/test commands, generated compiler commands, host ELF
dependencies, outputs and source hashes. Both final configurations build;
all **12 CTest checks pass**: ten C++ cases, receipt-schema validation (two
emitted receipts plus five invalid mutations) and the changed-input mock smoke.
An initial CMake package-version check failed because its format string was
expanded by CMake; bracket quoting fixed it before SYCL compilation. No native
binary was produced or run. The native target is OBJECT-only by default.

To reproduce this CPU-only preparation, using existing tools and environment:

```bash
nice -n 19 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage1/packet3-prep/validate_build.py
```

All build outputs stay under this packet's ignored `build/` directory. The
validation script deletes that directory after recording success or failure.
No GPU execution, GPU enumeration, `/dev/dri` access, server, systemd operation,
port 8188 access, LTX-unit operation, weight download or environment install was
used. All compilation/tests ran at nice 19 with `OMP_NUM_THREADS=2`, at most two
build workers. There is no remaining scratch or committed build output.

## Attention gate correction

**Sigmoid is the full-attention output gate.** The retained official 27B
config names `Qwen3_5ForConditionalGeneration` and contains
`output_gate_type=swish`. The corresponding official Transformers
[`Qwen3_5Attention` source](https://github.com/huggingface/transformers/blob/536ecc007387a50e77603bb5d92100e9b07514cc/src/transformers/models/qwen3_5/modeling_qwen3_5.py#L804)
uses sigmoid; neither that modeling file nor its configuration implementation
reads `output_gate_type`. [Evidence](gate-evidence.json) pins URLs, commit,
SHA256s, exact source lines and the unchanged publisher config identity.
Only source and metadata were read, without importing model code.

The [packet 1 contract](../packet1/tensor-contract.json),
[design](../../DESIGN.md), and [packet 1b reference](../packet1b/reference/math.py)
now distinguish effective sigmoid from unused swish metadata. GDN gated RMS
and FFN SiLU remain unchanged. Three added CPU tests check the evidence binding,
zero/negative gates (which distinguish sigmoid from swish) and the full
attention path with one key and constant values. The original receipts remain
historical; [packet 1's corrected check](../packet1/check-receipt-gate-correction.json)
and [packet 1b's corrected suite](../packet1b/test-receipt-gate-correction.json)
bind the current contracts: **35 parser cases and 96 CPU tests pass**, including
the three new gate tests. Certified device fusion/cast parity remains U5.

## First separately authorized native window

The coordinator must first resolve the host halt, authorize an exclusive
native window, identify the intended physical card, admit host/device memory,
and record fresh health and a kernel-log start boundary. This README is not
that authorization. No service or resident model belongs in this smoke.
Build/link the smoke in that future window (not done in this preparation):

```bash
nice -n 19 env OMP_NUM_THREADS=2 cmake -S experiments/own-xpu-runtime/stage1/packet3-prep -B experiments/own-xpu-runtime/stage1/packet3-prep/build/native -DOWN_RT_HOST_ONLY=OFF -DOWN_RT_BUILD_NATIVE_SMOKE=ON
nice -n 19 env OMP_NUM_THREADS=2 cmake --build experiments/own-xpu-runtime/stage1/packet3-prep/build/native -j2
```

The **first native execution command**, from the repository root, is:

```bash
nice -n 19 env OMP_NUM_THREADS=2 experiments/own-xpu-runtime/stage1/packet3-prep/build/native/own-rt-smoke --enumerate --card 0 --receipt experiments/own-xpu-runtime/stage1/packet3-prep/build/native/first-native-receipt.json
```

Preregistered pass criteria: exactly one owned in-order queue on the admitted
card; two changed 4 KiB round trips byte-exact; peak requested census 4,096
device bytes plus 8,192 pinned bytes; no census lifetime violation; all events
drained, allocations released, final marker completed, events/queue/contexts
released in order; receipt validates, `safe_to_exit=true`, code 0; supervisor
confirms the process exited, card idle and **zero new** Fault response, CAT,
engine-reset, coredump or GuC hard-lockup lines in the complete postflight
window. Preserve the receipt, census, exact binary hash, host/boot/card identity
and journal evidence. A timeout, mismatch, refusal or new fault fails the
window; retain evidence and do not retry, hard-kill, reset or reboot
automatically. Full packet 3 still needs separately admitted native coverage
of every release category; this tiny first smoke cannot qualify a model.
