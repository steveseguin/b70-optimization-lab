# Packet72 attention output

The gate selects one class: the shared attention output kernel across18 GDN
and6 QSA layers per half. Rank1's estimated excess at555 GB/s is0.30973 ms;
rank0 is0.26006 ms. This narrowly qualifies on rank1. QKV, Z and Q-gate fail
the requested0.3 ms threshold. HC/recurrence mechanisms rejected in packet67
are not reopened. See [bandwidth evidence](BANDWIDTH.md).

The source is copied from packet70, which uses packet65's wide64 experts.
The control keeps packet70's draft-HC, batched rollback and24/24 placement.
The new code changes only Q6_K6144 attention-output partial sums. Its final
BF16 conversion and four-stream combination use the unchanged production
finishing kernel. No expanded float buffers, changed quantization, compressed
KV, extra model work or draft changes are introduced.

Each physical lane now owns two adjacent original logical chains. It loads
16 raw signed8 codes, one shared F32 scale, and16 raw BF16 inputs. Eight input
words are loaded as32-bit integers and their halves are extracted. Each chain
retains its original `step → j` sequence of separate multiplies and adds.
The two completed chains form the first adjacent-tree level; the remaining
tree16 is exactly the rest of tree32. Each of four Split4 partials still goes
to the original global scratch location. The final `(p0+p1)+(p2+p3)` and BF16
rounding remain unchanged. Inputs without four-byte alignment fall back to
production before submission.

| Geometry | Production | Candidate |
| --- | ---: | ---: |
| Work-items/group |256|64|
| Physical lanes/partial row |32|16|
| Logical chains/physical lane |1|2|
| Workgroups for2560 rows ×4 parts |1280|2560|
| Total subgroups |10240|5120|
| Decoded float workspace added |0|0|

These are launch geometry totals, not measured simultaneous occupancy.

The [offline BMG-G31 report](register-report.json) compiles the checked engine
translation unit with its strict floating-point flags. Both partial-sum
kernels configure128 GRFs and have no scratch messages or spill declarations.
Production has9 static load instructions; the candidate has7, including the
three argument loads in each. The body falls from6 to4. The finishing kernel
is shared and unchanged. These are static counts, not dynamic load counts,
physical DRAM traffic or installed-driver occupancy.

The first version had13 static loads: its BF16 vector inputs became eight
scalar word loads. Reading raw32-bit input words gives two wider input loads
and removes that regression. [Initial source and report](evidence/initial-wide/)
are retained as a negative compiler result. No version was run on a GPU.

[GNU and Intel checks](evidence/cpu-byte-identity.json) each run twice:24 full
operator cases per run, including2560-row geometry, controls, NaN payloads,
infinities, subnormals and signed zero. Raw FP32 logical chains and the
regrouped adjacent tree are compared before BF16 rounding. Target device
identity and performance remain for the coordinator's13-check screen.

`combined` is an explicit alias of `attention-out`, because there is only one
new mechanism meeting the selection rule. LaneA runs both as fresh lifetimes.
LaneB uses the canonical alias only if the mean of both exact laneA candidate
screens beats the mean of its two controls. There is no best-alias cherry-pick.
