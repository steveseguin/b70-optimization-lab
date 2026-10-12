# Independent raw ABI review

Review scope: read-only inspection of packet22's typed raw bridge and packet29's
unchanged current kernel submission sources. No compilation, device execution,
device discovery, driver initialization, or native handle access was performed
by this review. This review does not transfer packet22's CPU ABI qualification
to packet34.

## Decision

Raw replay is blocked for the unchanged packet29 sources. Keep raw unavailable
and reject an explicit raw-mode request before device selection. SYCL graph
capture may record the original submit calls; a raw regular Level Zero list
cannot obtain their arguments through the existing public submit interface.
The blocker is missing export/instrumentation in these exact current sources,
not a fundamental claim that anonymous-lambda ABI can never be bridged.

## Exact missing pieces

Packet22's `raw_typed.hpp::append_typed<Name, Functor>` requires a concrete
kernel name and the concrete value-cloned functor, compiler
`CompileTimeKernelInfo<Name>` capture metadata, explicit group/local sizes,
one `RawLocal {bytes,elements}` for every local accessor, and an enumeration of
all owner device pointers including pointers nested inside aggregates.
Packet22 changed its own eight kernel entry classes to named functors and added
`raw_append`. Its `backend-notes.md` qualifies those eight entries only.

Current packet29 contains no `raw_append` hooks or `.packet22abi` manifests:

- `p28/submit.cpp::Kernel::submit` uses a locally scoped anonymous checked
  lambda, a one-dimensional local accessor and required subgroup size 32.
  `Finish::submit` is another anonymous kernel when split-4/wg32 is selected.
  Measured dispatch selects paired expert gate/up and many p28 dense families.
- `specialised_submit.cpp::Kernel::submit` uses anonymous range kernels.
- `round2_submit.cpp::Kernel::submit` has distinct subgroup/local-memory
  variants; `Simple::submit` is another local-memory variant.
- `adapter.cpp::SimpleNew::submit` and `Glue::submit` have separate anonymous
  range, single-task and local-memory kernels.
- `native.cpp::Kernel::submit` captures `Shape`, `Args`, and a local accessor.
- `runtime_kernels.cpp::Step::submit` captures `Spec` and its pointer array.
- The selected expert-down R5 path links inherited packet10 kernel submissions;
  `packet10-kopt5/kernels.cpp` likewise has anonymous SYCL submissions.

`ownrt::SyclOperation::submit` supplies an event, not its kernel object,
compiler capture descriptor, argument bytes, or raw launch descriptor. A
separate wrapper outside these translation units cannot reconstruct that
missing typed information from the event. Linking packet22's recorder does not
instrument packet29 automatically, and substituting packet22's Batch or other
old entry classes would violate the current-kernel workload identity.

Packet22's final ABI gate verifies final ELF-embedded SPIR-V signatures against
its manifest. Its old 8/8 model and 1/1 R0 receipts say nothing about the current
p28 templates, R5 expert down, specialised, round2, or adapter entry classes.
Enabling dead-argument preservation alone does not create manifests or export
argument values. The current packet29 capture-size guard limits lambda size;
it is not a raw ABI gate or a native argument-order contract.

## Feasible future qualification

A future separately reviewed source delta can extract each exact current kernel
body into a named functor shared by its direct submit and typed raw append,
without changing arithmetic or geometry. That is a source change and should
not be presented as unchanged packet29 linking. Alternatively, an upstream
supported interception interface would have to provide equivalently complete
and compiler-bound descriptors; none is exposed by the current interface.

The future gate must:

1. Enumerate every actually selected template/finish/control entry in the
   measured half-token dispatch, not assume eight generic packet22 entries.
2. Assert `-fno-sycl-dead-args-optimization` and all precision flags on every
   affected compile and final link; assert each by-value capture is <=1024 bytes.
3. Seal the final executable and compiler-produced ABI manifests. Run the
   packet22-style final-ELF/SPIR-V gate with this new entry set; check count,
   order, storage class, exact aggregate size, by-value attributes, local
   accessor expansion and capture bounds. Unknown kinds must fail closed.
4. List every nested device pointer, validate owner allocation generation and
   extent, and retain SYCL kernel/module wrappers through raw-list destruction.
   Explicitly preserve geometry, subgroup attributes, required local bytes and
   device-indirect residency. The compiler metadata remains the authority for
   host capture offsets; SPIR-V does not independently establish them.
5. Preserve the same in-order dependency semantics with barriers/events in the
   regular list; independent append ordering is insufficient evidence of the
   required global memory visibility without the recorder's synchronization.
6. On the owner's device window, run the direct equivalent first in the same
   process, validate every mutable byte for every iteration and changed control
   block, and only then admit raw replay. Check native argument count at runtime
   and preserve the recorder's drain/list/kernel/event/context teardown order.

The ABI gate is necessarily incomplete without the real current-kernel export
step. Do not replace it with a gate over surrogate kernels or claim native
arithmetic parity from SPIR-V signatures. Recording, native argument behavior,
exact output parity and replay timing all remain device-window questions.

## Dependency observation

Packet29 `backend.hpp::Context` creates in-order queues. Its `dependencies`
validates that supplied handles belong to the target queue and returns an empty
SYCL event vector: queue ordering serializes the same-card stream. Cross-card
dependencies are rejected here; the owner drains at card transitions. A
one-card benchmark should preserve that actual ordering and should not claim
packet29 submits an explicit per-kernel event chain to the driver.

## Packet34 capability gate and capture review

`raw_abi_gate.py` passed four CPU-only fail-closed tests. Its
`raw-abi-gate.json` binds the current measured dispatch, current submission
sources, inherited expert-down source and packet22 bridge by SHA-256. It rejects
the historical packet22 8-entry receipt, an empty receipt and a purported
current receipt even when `passed` and `qualified` are asserted. It also checks
that the reviewed current entry sources still lack raw hooks and named exports;
a future source adaptation fails this audit and requires a new review.
`passed=true` means these refusal tests passed. `raw_available=false`,
`qualified=false`, and `native_abi_gate_passed=false` remain explicit.

Source inspection of the initial `backend34.hpp` finds one newly submitted
kernel: the empty marker, passed through `packet26::checked`. All workload
submissions delegate to the current operation's `submit`. `mirror.py` applies
the existing packet29 overlay and by-value `checked` capture guard to local
build copies and records source hashes. A closure-wide final compiler-symbol
capture-size gate remains necessary: merely inspecting this new backend does
not prove the sizes of every inherited/current lambda. This reviewer did not
compile or inspect a final ELF. The native parser did not yet exist at review
time; its raw-mode rejection before device construction is an independent gate,
not claimed by the capability tests above.
