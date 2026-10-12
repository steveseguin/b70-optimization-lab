# Independent event and lifetime review

The reviewer implemented the window/K2 protocol work, not the submission overlay.
This was a read-only source review of the final eventful prepared path. No device
program, discovery API or device node was used. No new source defect was found
within the admitted single-issuer, two-card resident lifetime.

| Check | Finding |
| --- | --- |
| Real event ownership | The concrete prepared callback calls `queue::submit`, puts its returned real event in the native ledger, and returns the matching process-unique handle. Device::issue puts that handle in the owner ledger. Prepared copies do the same through `queue::memcpy`. |
| Preparation placeholder | Context::prepare ignores the SYCL return from operation submission while SubmissionCapture is active and retains only the captured command group. The default event returned by prepared_submit never enters a native or owner ledger. Owner capture returns a separate sequence index for ordering captured operations; Engine::finish ignores those while preparing. Nested/multiple native captures throw and the RAII scope restores its pointer. |
| Capture lifetime | The preparation-time virtual factory copies the concrete command group into the final callback. Its temporary factory object can then die. The callback owns scalar/array captures and borrows allocation/queue/backend-state pointers from its owner. The reviewed handler census and native implicit-this compiler gate exclude transient operation/binding-span references. |
| Sticky asynchronous error | The native callback locks the backend error mutex and rethrows its stored exception before submission. Copies call the same backend check. Completion, bounded wait, profiling and synchronization also check it. Device::issue records synchronous failures in the owner fault latch; admission then closes. An error arriving after the pre-submit check is caught at a subsequent issue or drain, not assumed absent. |
| Device sticky status | The normal token boundary drains and reads both sticky error and greedy result before accepting the token. Checked mode drains/readbacks at retained layer ends and reports the layer label. A status failure is not accepted as a token result. |
| Capacity / application allocation | Both event ledgers reserve 16,384 entries before issue. Owner admission and the native callback reject capacity exhaustion before submission. Prepared copies perform the same check. Recording successful work uses existing vector storage and the fixed event-card ring; there is no issue-path map insertion or reserve. Library-internal SYCL allocation is outside the CPU proof. |
| Card-switch ordering | Engine::issue_site drains before each card change and before captured peer copies. Its drain waits for the tail, then owner retirement checks every retained event and backend synchronization waits both in-order queues before clearing ledgers. Device::issue also rejects a retained preceding event from another card. Removing predecessor depends_on is valid only within these unchanged in-order queues and this fence rule. |
| Allocation invalidation | Capture validates both copy endpoints and all compute allocations. Owner identity and process-unique generation are checked before invoking callbacks. Release refuses pending work and changes the generation before freeing; shutdown quiesces admission. The new-owner-at-same-address test rejects stale callbacks. |
| Retirement / teardown | Events are not cleared while pending. Retirement synchronizes before clearing native and owner records. Shutdown drains, releases owned resources, waits a real final idle marker, then releases events, queues and context. A failed/uncertain drain retains ownership for the supervisor; no hard kill, reset or retry is introduced. |
| Failure before teardown | Main writes failure text and a failed receipt with teardown_pending before shutdown. Fixture failure handling writes its pre-teardown snapshot before drain/release. A teardown failure cannot create a passing window receipt. |
| Profiling and budgets | Class timing retains each native event and checks its actual execution interval against the four-second submission budget. Token mode retains completion events but has no individual timestamp/budget measurement; queue-wait and outer watchdog bounds remain active. This distinction is explicit in LIFETIME.md and the receipts. |
| Eventless forms | Neither submit_without_event nor nd_launch is used in this implementation. There is no fabricated completion marker. Adopting eventless work would need a separately qualified segment-completion, fault and lifetime protocol. |

The source agrees with [LIFETIME.md](LIFETIME.md). Application issue is one
indirect callback followed by direct submission of its concrete command group;
the factory's virtual call occurs only during preparation. The single issuing
thread owns ledger mutations. The asynchronous handler mutates only its guarded
sticky error, not the ledgers.

The independent owner/copy sanitizer tests and CPU protocol tests support these
source findings, but they cannot qualify the driver. Native asynchronous-error
delivery, queue completion under a fault, checked layer localization, per-kernel
profiling budgets and SYCL allocation/submission cost remain coordinator device
window gates. A CPU pass or unchanged SPIR-V does not substitute for those tests.

Reviewed source bytes:

| File | SHA-256 |
| --- | --- |
| prepared_submission.hpp | `41405cfc3c10727e245536993f647601b99705cdc9ac070e29f2ef695ffed2b9` |
| backend.hpp | `0496927e624ec32e44be489d7e1ffe3248ecf8d6021ff92f791d0619e02760e4` |
| owner.cpp | `c435f1c472cc45e56d39fca13cce2c53f32a51ccde5fc5bff529e5671e2f978d` |
| owner_retire.cpp | `e35c366f640d8909b519891fa814aa80228b01ce69bd19ccdf00a8d13cae0da2` |
| LIFETIME.md | `be2be92876fcf8f43061db533be1b2234658cd2312b007226bb4c07859c37848` |
| main.cpp | `5cc3286b9d263225542000600f4f6758fe4b9dc0bd20a6888eee9897c50bf6fd` |
