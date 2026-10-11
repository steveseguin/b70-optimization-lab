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
