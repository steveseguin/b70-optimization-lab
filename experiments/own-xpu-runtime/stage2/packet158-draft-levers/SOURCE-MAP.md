# Packet136 draft source, work and byte accounting

Design only. Paths below are relative to `../packet136-record-bundle/` unless
another packet is named. Line ranges refer to the files hashed in
`evidence/source-audit.json`. The active selection is `selection.json:18–65`:
rank1 draft, 24/24 target, BF16 KV, fixed **80,128-row** expanded-Q6 prefix,
unchanged `iq3-p49-split32-v1`. Target and draft INT8/BF16 formats are different;
none of the target's IQ2/IQ4 kernel figures price draft kernels.

## Group census and current implementations

The grouping is exactly packet157's `v5/native/split_timing.hpp:8–20`.
In particular attention's output projection belongs to **attention projections**;
the input group includes attention HC, routed experts includes FFN HC and the
ordered MoE/combine, and final norm includes final HC. These names do not mean
one kernel each. `mtp.hpp:75–89,190–208,231–242` prepares and issues them.

| Group | Packet136 call sites | Selected kernel source and real shape |
| --- | --- | --- |
| Input norm / embedding mix | `mtp.hpp:64–73,113–121,190–195,228–230` | `mtp_kernels.cpp:62–93`: hidden norm width10240 and merge; `specialised.hpp:77–112`: embedding/HC norms; `mtp_kernels.cpp:12–58`: BF16 embedding 2560×2560, hidden **4×(2560×2560)**; `p59_draft.hpp:50–98`: HC low320×10240 and inject4×10240; `p59_hc.hpp:6–30`: fused gate10240×320 plus four-stream mix. Existing low/activation and gate/mix fusions remain selected. Input copies/host embedding decode are outside packet157's kernel group. |
| Attention projections | `mtp.hpp:104–138,140–152` | `p33_submit.cpp:9–80,105–111`, `p33_candidates.hpp:78–104`: qgate12288×2560 BF16; `mtp_kernels.cpp:12–58`: k/v/iq512×2560 each, ik128×2560, output2560×6144. The production dispatch only special-cases `p33.dense.segment`; other draft dense cases use `mtp36::linear`. |
| Attention | `mtp.hpp:140–152`; `adapter.cpp:294–297,310–322` | `p42_tiny.hpp` prepare/pool through `p42_submit.cpp:62`; `round2.hpp:10–29` QSA select (4 index heads, dim128, pooled length C/4, stable block ties); **`p49_qsa_submit.cpp:14–48` → `p49_qsa_kernel.hpp:22–30,43–73`** admit, fixed32 score/softmax/value tiles, combine. 24 query heads,2 KV heads,dim256, BF16 cache, budget2048+tail3. `adapter.cpp` HC combine and `specialised.hpp` unchanged. `p30_attention.cpp` is NOT the selected draft value path. |
| Routed experts | `mtp.hpp:98–100,112–138,159–161` | `mtp_kernels.cpp:12–58`: selected ten of512 experts, paired gate/up each640×2560, down2560×640, INT8 codes plus FP32 scale per16. `mtp.hpp:140–152` and `adapter.cpp:268–273` select `route42` via dispatch implementation6; router512×2560; gather/status checks in `adapter.cpp:136–170,173–233`. `mtp_kernels.cpp:105–118` activation and ordered MoE; HC.f uses the same norms/low/gate/inject as HC.a. |
| Shared expert | `mtp.hpp:123–138`; `mtp_kernels.cpp:105–118` | BF16 gate/up640×2560, down2560×640, shared router1×2560. Down uses `p33::submit` at selected segment dispatch; other three use `mtp36::linear`. Separate rounded SiLU product remains production. Shared blend itself belongs to routed group's MoE event. |
| Final norm / HC | `mtp.hpp:113–121,140–152,232` | Norm4×2560; HC low320×10240 and gate10240×320 via `specialised.hpp:101–112`, `p59_draft.hpp:50–98`, `p59_hc.hpp:6–30`. No inject here. |
| Prefix head GEMV | `mtp.hpp:104–111,176–187`; `p56_prefix.hpp` | `p33_submit.cpp:43–80,105–111`, `p33_candidates.hpp:78–104`: `p33.dense.segment`, variant6, **80128×2560**, expanded Q6 useful fields3200 B/row, storage3380 B/row. Resident target head is shared, not duplicated. Target full head is unchanged. |
| Argmax / publication | `mtp.hpp:149,244–279` | `round2_submit.cpp:99–128,131–148`: two-stage finite-checking stable argmax, lowest index on ties. Begin/commit through `adapter.cpp`. Two ordered4-byte device→pinned copies; polling reads only after the final copy completes. Packet122 excludes these copies; packet157 includes their events. |
| Host issue | `mtp.hpp:211–242,244–279` | Context recapture at32-position boundaries, two drains around hidden copy, one bounded embedding-row read/decode/upload, prepared command iteration, publication issue and later polling. CPU work and device execution overlap. `draft_issue=1.571 ms/cycle` is packet154's control host median, not GPU arithmetic. |

## Bytes and FLOPs per draft

[ROOFLINE.md](ROOFLINE.md) gives all eight groups' byte totals, measured
times and signed gaps. [roofline.json](roofline.json) preserves both processes.
The base census is packet122's `roofline.py:8–48`, checked against packet136
shapes above. It counts **unique useful fields and activation/state reads and
writes**, not DRAM transactions. The head has256,409,600 useful weight bytes
and270,832,640 storage bytes. Neither is a measured bus counter.

The following is a reproducible **leading arithmetic work count**, using
two FLOPs per multiply-and-add pair. It is not an instruction count or a claim
that scalar FP32/deterministic transcendental kernels attain a tensor peak.
Extra reductions, elementwise work and special functions are stated separately;
they must not disappear into an invented precise compute roofline.

Let H=2560,L=320,M=640,E=10,N=80128. For attention let C be occupied tokens,
B=floor(C/4), n=4 min(B,512)+(C mod4), t=ceil(n/32).

| Group | Leading FLOPs/draft | Remaining arithmetic / comparisons |
| --- | ---: | --- |
| Input norm/embedding mix | **78,725,120** = 2×5H² + 2×(L×4H+4H×L+4×4H) | Norm squares/adjacent sums and two gain multiplies per element (H+4H+4H elements); rsqrt/epsilon; low SiLU320, HC sigmoid10240, four ordered mix terms/H; merge4H additions. All BF16 boundaries stay. |
| Attention projections | **102,891,520** = 2H×(12288+512+512+512+128+6144) | Fixed per-row tree32 adds beyond chain additions, BF16 stores; no tensor-engine arithmetic substitution. |
| Attention | Index dots **1024B**, QK **12288n**, PV fixed32 tiles **6144×63t** (32 multiplies+31 adds per dimension/tile) | Index ReLU and head-order sum; QK adjacent trees and /sqrt256; tile exp/subtract and max, denominator tree32; combine tile scale factors, ordered max and padded tree, exp/divide, gate sigmoid6144. Plus prepare/norm/RoPE/pool and HC combine. Integer stable-ranking comparisons up toB². At C128 these three dominant terms total3,153,920; at C4096 total50,987,008. Different operation costs forbid a single honest numerical compute-time floor. |
| Routed experts | **114,114,560** = 2E×3MH + 2×512H + 2×(L×4H+4H×L+4×4H) | **49,152,000 additional FP32 scale×INT8-code multiplies**, tree32 per output, route softmax512 and normalized top10, ten ordered expert terms per H; SiLU6400; FFN HC norm/mix/inject and shared blend. IDs/order and exceptional-value rejection stay fixed. |
| Shared expert | **9,835,520** = 2×3MH+2H | SiLU640 plus multiply, tree32, BF16 stores. Shared sigmoid/blend counted with routed MoE above. |
| Final norm/HC | **13,107,200** = 2×(L×4H+4H×L) | Norm10240, SiLU320, sigmoid10240 and four ordered terms/H. |
| Head GEMV | **410,255,360** = 2NH | **205,127,680 additional scale×code multiplies**, plus31N=2,483,968 tree adds. Scale decode and integer sign conversion are not FLOPs. No FMA contraction. |
| Argmax/publication | **0 numerical FLOPs** | N finite checks, comparison/tie/index selection; two-stage reduction and8 payload bytes copied (16 total read+write bytes). Not a zero-time operation. |
| Host issue | GPU FLOPs **not applicable** | 2560 embedding elements decoded and rounded; token format sets decode cost. Hidden copy20480 B read+write=40960 B, embedding upload5120 B payload, publication8 B payload. CPU/file/PCIe latency cannot be divided by device copy bandwidth. |

The matrix expressions count each RHS independently. Their logical matrix
weight reads before cache reuse are 78,725,120 B for the input group's four-RHS
case including its unchanged HC (unique useful group reference39,774,088 B
also includes other fields). For the **changed hidden projection alone**, the
precise useful-weight ratio is52,428,800→13,107,200 B; saved logical
loads39,321,600 B are not a measured DRAM saving.

## Reference time, measured kernels and gap interpretation

537 decimal GB/s is the lab copy reference (`../packet2/README.md:160–171`,
`../packet110-class-roofline/ROOFLINE.md:3–11`). It counts read+write bytes.
`reference_ms = useful_bytes / 537,000,000`; `gap_ms = measured_ms-reference_ms`.
Keep the sign. The prefix head's approximately0.445 ms is **below** its0.477793 ms
copy reference; caches, differing traffic and the empirical copy reference
make this possible. This is not an exact physical lower bound.

Packet122's two authenticated device runs are the best completed per-kernel
measurements available at the initial audit. Aggregation uses forty complete
step sums per process/context and the exact packet157 group mapping. The
0.230 ms attention figure in the October18 note mixes context information;
use the context-specific event rows here, not that number for a128-token group.
No target-GEMV figure is silently substituted for a draft INT8/BF16 figure.

Packet157, if completed, supersedes the timing column only after complete
C/T/C/T/C, thirteen exact outputs/view, identical proposals, valid clock/group
census and instrumentation-overhead review. Use equal prompt/view means to
match its analyzer; average **analytical** bytes at each included position.
Its raw-time top-two list need not equal its largest-gap list. Host group sums,
device sums and host-unassigned time must remain separate.

For packet154 the only defensible host bounds are **0 to the observed enclosing
host time**, with overlap and required work deducted by a future matched probe.
There is no measured CPU throughput roofline; write host gap as **unresolved**,
not1.571 ms of removable overhead. The1.227 ms/interval draft overlap and
0.423078 ms/hit goal remain different denominators.
