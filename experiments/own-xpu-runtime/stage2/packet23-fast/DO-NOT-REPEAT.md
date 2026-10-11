# Packet 23 negative-result index

| Arm | Outcome | Revisit condition |
| --- | --- | --- |
| per-launch profiling queries left on in a speed run | Closed: approximately 9800 queries/token contaminated packet18 wall time. Use token mode for speed; launch mode is distorted diagnostic evidence. | Separate diagnostic question only. |
| Reusable SYCL dependency vector surviving context release | Review caught a new borrower lifetime hazard before any device run. clear_events now drops dependency_storage before native context release. | Preserve explicit borrower inventory with any new cached object. |
| Fixture schema renamed only in wrapper | CPU review caught incompatible K1 receipt expectation. The unchanged packet21 fixture schema is retained. | Change both producer and validator together. |
| Full resident CPU or real-model sanitizer gate during GPU windows | Forbidden by this task's memory budget. Carry original receipts only with source proof and a fresh streaming check. | Separately admitted memory window. |

ASan first launch could not reserve its virtual shadow under the 8 GiB address-space
cap ([receipt](guard-first-attempt.log)); rerun of the small bounds fixtures passed
without that virtual limit. This was not physical memory pressure. The streaming
model gate kept its 8 GiB address-space limit and peaked below 0.8 GiB RSS.

| Repair arm | Outcome | Revisit condition |
| --- | --- | --- |
| kernel captures a large parameter block by value | W0 device compiler rejected 6036 ABI bytes against 2048. Tables now live in owner-tracked device allocations. Every kernel functor passes a compiler sizeof(F) assertion and the source mirror refuses an unwrapped call. | Keep the mechanical gate; K0 still checks device ABI/JIT. |
| first device contact of a new binary without a JIT build step | Closed. Host linking cannot see the B70 argument limit. Mandatory K0 builds the shared kernel image set before K1/W0/model work. | A new binary requires a new K0 receipt. |
| owner parks during unwinding before the error is reported | Proven control-flow defect: compute records fault_, old shutdown refused cleanup immediately, destructor parked before outer catch. Catch within each owning scope, persist diagnostics and results first, drain once, normal failure exit when zero work remains. | Keep first-build and retained-borrower CPU controls. |

K1 attempt a's triggering exception remains a hypothesis. The original output
contains no exception text. Its GEMV component passed 553/553. No retained
external SYCL borrower was found in the non-GEMV fixture: CopyEngine contains an
owner reference only; Ref/Fused/adapter operations hold scalar metadata/pointers.
