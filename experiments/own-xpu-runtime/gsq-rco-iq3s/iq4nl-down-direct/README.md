# IQ4_NL expert-down: direct global row reads

This is source preparation, not a qualified kernel or speed result. The candidate
removes p6's cooperative 360-byte row copy into local memory and its workgroup
barrier. It retains four SG32 subgroups per workgroup, the exact existing
`decode8`, `lane_dot`, adjacent reduction tree and BF16 conversion. Weights remain
packed IQ4_NL, gathered inputs remain separate for all ten route slots, and no
allocation is added. No model payload has been read for this candidate.

The prior eight-generated-position attribution measured 31.614377 ms for IQ4_NL
expert-down (312 events, 16.45% of the 192.148198 ms routed sample). This identifies
a concrete path, not its full-request share or a predicted speedup. The trace
predates the IQ3_XXS gate/up change. Direct global loads might lose the staging
path's coalescing benefit; only a matched native comparison can decide.

`selection.json` preserves all 39 actual graph sites, including their active/error
inputs. The current p6 Matrix consumer does not bind or mutate active/error.
Its strict candidate geometry is type20, 512 experts, N2560/K640, ten slots,
span2560, BF16 input/output, SG32, no diagnostic FP32. Integration must additionally
match the exact labels and weights in this manifest; no Engine integration exists
here yet. Each packed bank is 471,859,200 bytes, with 921,600 bytes per expert.

`prepare.py` derives `direct.hpp` from the hash-pinned current private p6 source.
`direct.patch` exposes every change. The inherited live-device extent/alignment,
unique-allocation, overflow, route/status and device subgroup/workgroup guards
remain. The original 1,472-byte local-memory admission check remains conservative,
although the candidate requests no local accessor. Descriptor and pointer capture
remain by value through `prepared_submit`. This header is intended for one entry
translation unit, like the existing isolated micro wrappers.

The source checks compare the exact inherited dot body, reduction/output block
and binding body. `proof.cpp` is a bounded CPU address proof using the unchanged
p6 decoder: all sixteen row alignments, representative half zero/subnormal/finite/
Inf/NaN scales, staged/global lane/tree/BF16 bits, compact routed backing with
invalid/duplicate/zero-length/tail routes, output sentinels and ten strict policy
refusals. It does not prove SYCL address-space behavior or universal NaN priority.
No equality tolerance or exceptional-value waiver is allowed.

The build helper defaults to printing its plan; `--build` is an explicit bounded
GNU CPU compile/run (nice19, CPUs8–15/24–31, thread variables2, 4GiB AS, 64MiB
retained budget, coordinator and 27GB floor). No runtime objects or device code
are linked. The source-only tests have run; compilation is pending root review.

The historical p100 IQ4 down-tile16 path is not an equivalent drop-in: it uses a
transposed packed layout, a different lane mapping and active/error failure
behavior. It is intentionally outside this single memory-access experiment.

Future minimal native discriminator: fixed layer0 expert-down, original per-slot
input/routes/full 25,600-element output and ten statuses, sparse authenticated
expert slices at their original IDs in one full-sized bank. Use equal excluded
warmups and balanced AB/BA orders; every output/status must equal both control and
saved baseline. No extraction or native harness has run or been admitted.

A future owner must publish readiness after actual native backend/context
construction and before any measured kernel. Its monitor must observe the exact
registered PID/start-time holding the target DRM node and issue a bound ACK before
execution. Readiness alone or an explicit unrelated admission FD is insufficient.
Keep the actual backend alive while awaiting ACK, with a finite cooperative
refusal deadline, preserved first error and positive backend drain. This closes
the prior micro's short-process observation race without changing its failed
qualification or weakening physical contact requirements. Root reviews the actual
backend retention mechanism before any new device admission.

Source identities and arithmetic authority are in `source-pins.json`; the exact
selection is derived from `graph/new-plan.json` plus `metadata/new-census.json`.
