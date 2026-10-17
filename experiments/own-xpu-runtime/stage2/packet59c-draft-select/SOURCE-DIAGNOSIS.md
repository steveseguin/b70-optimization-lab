# Why packet59 can lose inside the engine

The supplied screens are real engine evidence. Their bound summaries are in
[source-diagnosis-evidence.json](source-diagnosis-evidence.json). Against the
second packet56 control, packet59 loses 0.473564 class-balanced tok/s (1.012%)
and adds 0.410313 ms to the median hit cycle. The two controls differ by
0.003511 tok/s (0.0075%). The old 0.38 ms saving was a projection from different
kernels/conditions, not a device result for these draft kernels.

The acceptance **median** stays 0.787402. The summaries also show a small mean
change, 0.785433 to 0.784121 (two fewer accepted proposals across twelve
prompts). Keep both in later comparisons; do not describe every prompt's
acceptance as unchanged.

These are source-based hypotheses, not measured kernel attribution. The draft
executes M=1 on rank1 immediately after that rank's target half. It sees its
own BF16/INT8 weights, cache state and growing selected-token count. Target
IQ-format timings and isolated warm operator timings cannot price these swaps.

| Priority | Source mechanism | Why it could lose here | Switches / isolation |
| --- | --- | --- | --- |
| 1 | `p49_qsa_kernel.hpp`: split32 uses admit, tiles and combine; `p30_attention.cpp` variant1 uses two passes | Three launches instead of two. At a short selected-token count, setup and scratch traffic can dominate; the tiled path holds 64 value registers per lane and uses local barriers. The allocated 4K context is not the active attention length. | `qsa_attention`, in screen1 |
| 2 | `p59_hc.hpp`: gate/mix uses 128 threads for four output columns, a local BF16 gate array and a barrier | Saving a separate mix launch adds synchronization and serial four-stream sigmoid/mix work to the producer. Compare new gate with fusion off to separate schedule from fusion later. | Three `hc_*_gate` and `fuse_hc_*_mix`, screen2 |
| 3 | `p59_draft.hpp`: fixed256 norm uses one workgroup per row and nine barriers including the initial store barrier | Low launch count does not guarantee low latency. One or four workgroups provide little parallel work, with a long local-reduction dependency chain. | Five norm switches, screen4 |
| 4 | `Dense::output` / `tail`: low activation, attention combine and merge execute on the reduction's output lane | Split4 leaves one output lane per workgroup doing the fused tail. Attention loops over four streams and evaluates sigmoids there; removing a parallel consumer can lengthen the producer's critical path. | Ten independent fusion switches; screens1–4 |
| 5 | `Dense::chain`: expert virtual8/16 and BF16 virtual4 accumulate multiple logical lanes on one thread | More independent output rows can help throughput, but paired gate/up holds both chains and extra live state. Register pressure and rank1's just-used target working set may erase the isolated schedule's benefit. | `gate_up`, `down`, shared projections; screen3 |
| 6 | BF16 split4 HC inject has only four output rows | Four workgroups is little device occupancy; extra local scratch/barrier costs can outweigh the narrower sums. Target-format and draft-format schedules are different. | `hc_a_inject`, `hc_f_inject`, screen2 |

**Alignment is not the leading source explanation.** Production BF16 K values
320/640/2560/6144/10240 give row and activation strides divisible by 16 bytes.
The INT8 row sizes are 3,200 and 800 bytes, also divisible by 16. The draft
loader creates separate device allocations; its indexer slicing is copied into
those allocations, not retained as an offset alias. These facts do not prove
the runtime allocator's actual addresses or the compiler's load lowering, but
there is no source-visible odd stride to blame for every vector8 load. Do not
claim an observed unaligned-load fault or performance penalty without a device
address/assembly check.

Qgate has substantial BF16 traffic and expert arithmetic may still win; neither
is banked from a proxy. Prefix head and argmax are unchanged. A faster group
with different acceptance must be judged by both cycle timing and the fixed
suite's class-balanced rate. The four-screen plan partitions the changed
sites, so a group can be retained or rejected without quietly retaining the
whole slower packet59 draft.
