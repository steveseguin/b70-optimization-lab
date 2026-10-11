# Independent packet20 review

CPU-only source review. No device, discovery call, device binary, compilation,
parked-process interaction, privileged command, or GPU-related unit was used by
this reviewer. Final implementation findings and verdict appear below.

## Level Zero ownership contract

Primary evidence is the installed IntelLLVM 2026.0 SYCL headers and installed
Level Zero API header; successful compilation establishes API availability,
not B70 driver support.

- `stage1/packet3-prep/src/owner.hpp`: all submission enters the owner; borrowed
  raw queue and foreign untracked events are forbidden. `Device::shutdown` in
  `owner.cpp` drains tracked events, releases graph leases before arena storage,
  waits a final marker, then releases events, queue and context.
- `stage1/packet3-prep/src/sycl_device.cpp`: SYCL wraps an explicitly owned
  context with `ownership::keep`; its native context is destroyed only after
  SYCL event, queue and context wrappers. Packet20's extension must obey this
  ownership order. Independently created raw queues must be drained explicitly;
  waiting the SYCL queue cannot establish their completion.
- `/opt/intel/oneapi/compiler/2026.0/include/sycl/ext/oneapi/backend/level_zero.hpp`
  lines 125–159: `get_native(queue)` returns a variant containing either a
  command queue or an immediate command list. Never cast it unconditionally to
  a command queue. Borrow context/device handles, create owner-held raw children
  in that context, and never destroy borrowed context/device/queue handles.
- `/usr/include/level_zero/ze_api.h` lines 3187–3211:
  `zeCommandQueueExecuteCommandLists` requires matching context and queue-group
  ordinal, a non-immediate list, and no overlapping execution of the same list.
  A replay waits completion before changing input state and replaying again.
- Header lines 3036 and 3369: immediate lists use
  `ZE_COMMAND_QUEUE_FLAG_IN_ORDER`; regular lists use
  `ZE_COMMAND_LIST_FLAG_IN_ORDER`. Otherwise supply actual event/barrier
  dependencies. Ordinary append order is not an adequate dependency argument.
  A driver rejection is reported, never silently replaced by an unordered run.
- Header lines 7918–7925: kernel arguments are consumed at append time.
  Calling `zeKernelSetArgumentValue` after list close does not update recorded
  arguments. Per-replay values live in device memory behind fixed pointers.
- Header lines 3147–3157, 3500–3508, 4709–4718, 4971–4978,
  7340–7348 and 7734–7741 require completed references before destruction:
  release lists before their referenced events/kernel/module and allocations;
  release events before their pool, kernels before their module, fences before
  queue, then all raw children before the SYCL context owner closes.
- Header lines 5552–5608: timestamp events require a timestamp pool;
  conversion must use timer resolution and valid-bit wrap. Keep first/last
  timestamp events alive until queries finish and reset only after completion.
- Use finite polling deadlines, then retain ownership on an unproven drain.
  A timeout does not authorize freeing live USM, destroying an active list,
  killing a device process, or reporting success.

These findings were sent directly to the issuing implementation agent before
its first completed implementation.

## Fusion and replay exactness requirements

`packet17-detmath/core_v2.hpp` is the reviewed arithmetic authority:

- Every removed BF16 intermediate store retains an explicit BF16 rounding at
  the same expression point; no contraction or reassociation is introduced.
- Consecutive sites are not automatically safe to run as a multi-work-group
  fused kernel. A work-group barrier is not a global barrier. One work-group,
  serial exact core, or exact independent recomputation must preserve any
  whole-row dependency. Count-only fusion is a design lower bound.
- Route ordering is descending normalized probability with original ascending
  expert ID for ties. Ranking logits instead is not exact because rounded
  probabilities can tie despite unequal logits. Parallel ranks must compare the
  exact normalized v2 probabilities and use that tie rule.
- Removing expert input replication is exact only when each former
  `[expert_slot, column]` read maps to the same original BF16 input column.
  Route descriptors, expert IDs, weights and row reduction trees stay unchanged.
- QSA active lengths define reduction trees. Fixed-capacity replay must retain
  the same active-prefix tree, including its explicit missing-partner `+ 0.f`, and must mask
  inactive lanes before reads, exp and multiplication. Merely inserting zero
  terms into a larger tree is not a sufficient bit-exactness proof.
- Aliased storage cannot overwrite still-live sources. New fusion interfaces
  retain distinct intermediates or explicit scratch with documented live ranges.

## Final source review

Initial implementation findings and fixes verified in source:

1. **Fixed: asynchronous resource unwinding.** The first implementation caught
   exceptions outside a function whose local SYCL queue/graph owners and H2D
   stack source were already destroyed. Native code now retains explicit queue
   and executable ownership on failure, stores token-state/upload/readback
   staging in the backend, and holds the owner/process instead of freeing live
   resources. Success alone deletes the executable and queue.
2. **Fixed: asynchronous error data race.** The handler and reader now protect
   `exception_ptr` with a mutex, following Stage1.
3. **Fixed: replay workload not checked.** Every trial now restores known input,
   changes the device token-state sign, and compares BF16 output to a host exact
   recurrence after timing. Validation copies remain outside graph capture.
4. **Fixed: attention invalid-ID ordering.** Fusion now prevalidates every
   token's selected IDs uniformly in every head work-group before doing fused
   score/softmax/value work. Invalid partial score scratch is not claimed to
   match the original concurrently failing groups; valid-data arithmetic and
   sticky failure are the required contracts.
5. **Fixed: replay tree wording.** The frozen v2 tree performs explicit
   missing-partner `+0.f`; it does not simply forward an odd tail. The replay
   design was corrected to require the actual source tree.
6. **Fixed: plan identity.** The raw packet3 plan had 1,873 sites, whereas
   packet18 has 1,825. Packet18 explicitly combines expert gate/up at
   `main.cpp:365–379`; its two-launch `moe_combine` must also be retained.
   These differences can cancel in a total while corrupting fusion counts.
   The final DAG normalizes both and asserts every layer's physical census.
7. **Fixed: token-boundary counts.** Independent sequential scanning of the
   normalized DAG produced 1,971 frozen / 1,707 R5 launches under rule (i).
   There are 48 permitted joins: 46 same-owner layer boundaries, final layer
   to final norm, and initial streams expansion to first-layer norm. The first
   draft missed the last of these. Rule (ii)'s constructive schedule becomes
   926 frozen / 876 R5. Rule (iii) can retain those counts by folding the
   selected-probability finish into an existing later launch with one designated
   writer. The separately gated standalone routing prototype uses two launches
   and adds 48 launches/token; this integration distinction is explicit.
8. **Fixed: incomplete row validation.** The Python window now independently
   checks all 270 distinct method/workload/N/repeat combinations, launch
   denominators including the N=100 fusion tail, finite timings and verified
   outputs before clearing its latch.

The window's ldd-before-latch ordering, parameterized physical card, finite
journal polling, child-PID-only cooperative SIGTERM, no hard kill, retained
failed latch, and explicit incomplete-drain outcome were reviewed in source.
CPU mock tests test these branches without starting a native device binary.

Open limits: driver graph/in-order-list support is unmeasured; opaque runtime
and graph-pool device reserve is outside the explicit-USM census; a hung driver
call itself cannot be bounded safely by destroying the process; generic fused
single-work-group chains are correctness prototypes, not performance evidence;
the fixture suite is not an integrated full-model graph gate.
No device behavior is certified here.


## Final verdict

No remaining blocking source-level interop lifetime issue was found after the
fixes above. The Level Zero implementation uses the owner's borrowed native
context/device, owner-held raw children, explicit in-order dependencies, finite
completion polling, no overlapping replay of a regular list, and success-only
teardown. Raw first/last kernel timestamps use timestamp events and valid-bit
wrap handling. Timing endpoints precede validation/readback and serialization.

The unchanged v2 operator gate passes all 72 fixtures under GCC and IntelLLVM,
two fresh host processes each. All four output SHA256 values are
`8f81366702261e9f88ec0dc661042894f50592af1a41bf51aa0cc01ce4edee04`.
The gate includes six route fixtures, three attention fixtures, eleven
norm→activation producer/consumer boundaries, six real multi-site chains
(HC combine/norm→mix, conv→GDN→gated norm, and full QSA preparation through
attention, at T=1 and T=3), and eight control checks. Final source hashes were
independently checked against the fusion build receipt. The gate does not prove
every planned full-model layer binding or the unimplemented GEMV interfaces.

The arithmetic argument preserves explicit BF16 rounding, fixed reduction
trees, normalized-probability route ties, selected attention order and single-row
expert input bytes. Multi-work-group ordering is either preserved by a launch
boundary or avoided by a one-work-group correctness prototype. The low counts
are design schedules, not measured device launches or latency guarantees.

The prepared device window remains conditional on recovery and admission.
Actual B70 API support, strict total device-memory consumption below 64 MB,
completion below 60 seconds, and device exactness remain unmeasured. Explicit
USM below 64 MB alone does not close the opaque graph/runtime memory question.
