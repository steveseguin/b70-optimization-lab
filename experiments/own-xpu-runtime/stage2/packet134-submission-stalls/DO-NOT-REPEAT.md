# Packet134 boundaries

| Closed inference | Evidence | Revisit condition |
| --- | --- | --- |
| Treat 1.679 ms as speculative enqueue-loop starvation | 1.594 ms is snapshot-to-begin; only 0.085 ms is internal. [Attribution](ATTRIBUTION.md). | Matched low-overhead current-runtime evidence of material internal gaps. |
| Treat `host.command_gap` as idle host submission time | It includes pending rank1 drafting, suffix service and verification. [Source audit](README.md). | Measure the exact host region, without double-counting its device overlap. |
| Conclude drafting is free from a 0.007 ms publication wait | 1.276 ms of the pre-half host gap overlaps the earlier pending draft command. | Include `b.wait(1)` and draft host submission/startup separately. |
| Reuse the historical one-card 1,790 count | Current sampled rank0 halves each issue 564 target kernels. | Recensus the actual admitted selection and topology. |
| Rank speed levers from packet128b | Its 51.475 tok/s fails its own 52.2 overhead threshold. | Fresh adequately bounded or matched timing; no relabeling this sample. |
| Implement already-present prepared arguments or pure-spin waits | Packet35 preparation and packet61x wait mechanisms are in packet124c. | Identify and measure a concrete new delta. |
| Capture preparation's H2D or assume the lookup tables are device-resident | Host lookups/decode/uploads occur before target submission. | Separately prove exact inputs, lifetime and admitted memory fit. |
| Call this analysis a passed runtime candidate | No runtime changed or device ran. | Full brief gates, smoke and matched bracket for a real new implementation. |

The [closeout](CLOSEOUT.md) closes this lever for the retained evidence, not the lane.
