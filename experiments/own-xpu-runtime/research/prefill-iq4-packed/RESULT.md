# Grouped IQ4_NL packed logical lanes: close as small

2026-10-28, one isolated candidate; canonical sources untouched, no integration switch or production dispatch added. `packed-grouped-candidate.patch` preserves the standalone new header only; it is NOT a production-integrated patch. Same groupedT4 bucket, four canonical8column lanes perphysical lane, once/block worddecode/halfscale/local16float LUT, four logical accumulators preserving their sequence, firsttwo adjacentpair levels inregisters. SG32 packs four independent rowsets; remaining tree stays within eightphysical lanes/set. Ragged/dead rowsets still execute all subgroup reductions; no collective under a nonuniform row continuation.

Exact gate adapted existing prefill-experts/evidence/cputest/test_experts.cpp: 18scalarreference cases (K256/640/768, rows41, tokens1/7/32, fullroutes vs invalid/partialroutes), alloutputs bitwise and status equal. Then fullproduction512experts×2560rows×K640 with256tokens/top10: all6,553,600 outputs bitwise equal against existing xgroup1×4. Production routes use first256positions of actual archived `/dev/shm/ownrt-lab-experts/routes-4096.bin`, label blk.24.expsdown,458distinctexperts. `bench/routes256.bin` preserves those exact routes. Weights/activations are deterministic random finite, not model weights. Productiongate thus establishes kernel mapping/parity only, not model-state parity.

Existing decode-experts/kbench/harness.hpp reused with sixinterleaved rounds, eighthot/eightcold samples each,1.5s warmup. Median microseconds, tilekernel only (same bucket preparation excluded):

| | Hot | Cold |
|---|---:|---:|
| Incumbent xgroup1×4 |4913.8|4866.6|
| Packed four logical lanes/T4 |4504.1|4544.1|
| Improvement |8.34%|6.63%|

Prior actual rank0profile IQ4_NLdown1.1993s/12.848s target gives only~0.6–0.8% target-budget extrapolation, not measured end-to-end gain. Retain candidate, close integration; no expandedtile sweep or fullmodel load justified by this result.

Unit ownrt-group-iq4-packed-c43-20261028, invocation5ce7c7480aa54a218eafba2629c09b2f: exit0, TOTAL FAILS0; exclusive card43/renderD128. Passive before/after knownfault baseline matches, no holders afterward, no power/memory/service reload changes. Actual existing PP4 plan floors read and enforced:100GB availableRAM start,27GB rootfree,2GiB evidencefree. No fullengine build. Build: oneAPI2026.0 icpx, stdgnu++20 -O2 -g0 -Werror=return-type -fno-fast-math -ffp-contract=off -fsycl -fdenormal-fp-math=ieee -foffload-fp32-prec-div -foffload-fp32-prec-sqrt, engine/src include, -lze_loader. One pre-existing enum switch warning preserved in build.log.
