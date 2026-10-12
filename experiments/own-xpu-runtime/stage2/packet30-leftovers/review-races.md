# Write-race and subgroup review

CPU-only source review. No device executed. Reviewer: dense/fusion subagent, independent of route and attention implementation; small/fusion identity and guards separately reviewed by the route subagent. This is not device race-detector evidence.

- Route first stage: each `(chunk,lane)` owns one probability index. The second stage depends on the first event; no global memory rendezvous is assumed inside a launch. In stage two partition/block/lane owns a unique original element. Stable rank is a total order for finite probabilities, so only one element writes each selected rank and its descriptors. Each WG reconstructs selected values locally rather than consuming another WG's new stores. Two-launch WG64 has two independent SG32 partitions; inactive partitions still execute their denominator collectives and perform no output loop. Single-launch rank compares use shuffles at identical control points in all lanes. Nonfinite logits cause an SG-wide bad flag before any dependent tree. No route write race found.
- Attention Stage0: one WG owns `(head,slot)`; lane0 alone writes score. Stage1: one WG owns head and lanes stride disjoint slots. Value: one WG owns `(head,output-column)`; lane0 writes exactly one BF16 output. Merged score/softmax owns all scores/probabilities for its head, communicates owned values through subgroup shuffles, and does not read just-written global score memory. Every subgroup receives one broadcast admitted count; empty/invalid paths are uniform. All value and softmax subgroup loops have subgroup-uniform bounds. No attention write race found.
- Small: global SG ordinal chooses one matrix and row, and only lane0 stores that row. All 32 lanes in each SG take the same compile-time member branch. WG128 can put adjacent member types in different SGs safely because no WG barrier or local memory exists. Padded SGs do no collectives and no writes; active SGs remain uniform. Split partials are private lane registers. No small-kernel write race found.
- Fusion: stream is WG-owned; tiled `(stream,tile,lane)` outputs are disjoint. Each WG reads original stream/branch/gain inputs while writing separate combined/normed outputs. Recomputed reduction never consumes newly stored output. Mix global work item owns output column. Error writes use atomic stores and ordinary data outputs cannot overlap error/control/input ranges after validation.

Findings fixed: small/fusion argument guards now reject misaligned typed pointers and pointer-span overflow; fusion sticky error slot15 is classified as writable for output/input alias checks. CPU tests include invalid extents, shifted pointers, and overlap rejection. Parent G3 is responsible for invoking the corresponding raw-queue validator before each submission because raw USM addresses do not carry allocation extents.

Scope: no concurrent unrelated writer may mutate a submitted input or active/position buffer. The event DAG ensures each launch's inputs are stable. The guard is sticky but cannot authorize unsynchronized external control-buffer mutation. Device execution and byte comparison remain required.

Reviewed source hashes:

- `route.cpp`: `02b3200ed7f18b24e8223f31b49dfcac85763404bea5c1a8a2b1b3681eb29f10`
- `route.hpp`: `9d1d22d56bc16095d9a4639ee5e3609aacb5409683dd9768436288a20b099160`
- `attention.cpp`: `4517d33ac38e20aa3a28633c421a7488857f0ba1288b169ded55865d37cbfc7f`
- `attention.hpp`: `04fe9ccaf9da61d8a269b62d0c1f0cf8fb017622a959d21d6e12ef9372124f18`
- `small.cpp`: `89e0cafa20d1392bc54330ece0155e70945eaa1ab427db733d88cb3e26f0ce65`
- `small.hpp`: `001c189c164f163b1f31839912f98192bed753d11bd7fb9dea56e5b45330ac6b`
- `fusion.cpp`: `78098d1a5b633933898396ae237b70ccc0fc77f2ee3f37d3bf03de7e27ddfad0`
- `fusion.hpp`: `7bfb176a7fd9ec2bf3e8eb96b86d393002546af302c983a4296b042610f349b5`
