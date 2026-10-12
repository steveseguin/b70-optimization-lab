# Independent prepared-binding invalidation review

CPU-only source review. No device program ran. This review is independent of the
main host-path implementation. The owner/copy invalidation cases pass 13/13 under ASAN and UBSAN with leak
detection; [prepared-invalidation.json](prepared-invalidation.json) binds the
binary, sources, precision flags and exact commands. No device program ran.

| Invalidation source | Review |
| --- | --- |
| Allocation release / replacement | Arena release changes a process-unique owner generation before freeing; Device::issue rejects a different owner or generation before touching the prepared closure. Newly allocated IDs are monotonic; release/reallocate cannot silently preserve the old generation. |
| Owner destruction and address reuse | Every new owner starts with a process-unique generation. A placement-new owner at the identical address rejects the old command. Closed owners reject issue before invoking a closure. Tested under sanitizers. |
| Additional allocations | Existing allocations do not move when the arena row vector grows. Adding a new unrelated allocation does not invalidate existing bound pointers. |
| In-place token / position / history / cache contents | Pointers stay bound; kernels read updated contents at execution. This must not cause a binding rebuild. |
| FP32 input conversion reuse | Preparation starts with empty source caches. Lookup resets each card's cache; scheduled writes to a cached BF16 source invalidate it during capture. The resulting conversion launches replay each token, including the first use after prefill. |
| One-card layer staging and selected expert uploads | Explicit legacy path. Prepared commands are constructed only for two-card resident mode; one-card allocation changes cannot reuse these commands. |
| Dispatch / plan / shape / variant / topology changes | Engine owns const Options by value and a const Plan. Dispatch loads before construction and a saved dispatch snapshot is compared at each token boundary; a changed dispatch rejects work and requires a new Engine/repreparation. Resident binding maps are built before capture and are not reassigned by any admitted two-card execution path. Allocation release is independently generation-guarded. New dispatch/topology/shape/buffer layouts require a new Engine, which reruns preparation; one-card staging uses legacy execution. |
| Handler capture lifetime | All 28 transformed handler bodies capture values and have no p/deps/this/reference_wrapper references. The native build treats deprecated implicit-this capture as an error. That guard found an inherited packet7 Stream handler reading member copy; explicit copy=copy capture fixed it. All native translation units then compiled successfully. No kernel body changed. Host operation copies survive destruction of the original temporary in the sanitizer test. |
| Queue / context replacement | Prepared closures hold pointers to queues owned by the same Backend. Owner admission closes before teardown. Queues are not replaced during the resident Engine lifetime. |
| Capture dependency and erased-operation misuse | Foreign pseudo-dependencies are rejected; valid prior capture events remain ordered. A base-Operation call during capture is rejected rather than accidentally submitting work during preparation. Both paths are tested. |
| Checked/class modes | Extra checks/readbacks do not change allocation identity. Card-switch drain still precedes submission; checked reads localize sticky errors at layer ends. |

The initial argument-audit finding is corrected in source. `argument_block.hpp`
serializes all registered current host operation state, template/type identity
and geometry-driving fields, with GCC padding normalization. The independent
registry census covers 14 current operation definitions and 17 state members.
Owner audit records both legacy and copied argument bytes plus allocation IDs;
actual pointer blocks remain in the separate prepared-arguments log. This is a
closed registry: newly added operation members must extend its serialization
and census gate. Runtime mini/real-eight argument and sequence comparisons are
recorded by the main packet gates; this source review does not replace them.

No source invalidation finding remains open for the admitted resident lifetime.
Native prepared replay, queue errors and checked-mode localization still require
the coordinator's device windows. CPU mocks and native compilation do not prove
hardware execution or device timing.

The final native helper uses its virtual factory only during preparation. The
saved callback owns the concrete command group and directly calls queue::submit;
there is one application indirect call during issue. The earlier additional
virtual issue hop has been removed. Backend event/error state and queue pointers
remain borrowed from the same owner, protected by the admission/generation checks
above; callback ownership does not extend a freed backend's lifetime.
