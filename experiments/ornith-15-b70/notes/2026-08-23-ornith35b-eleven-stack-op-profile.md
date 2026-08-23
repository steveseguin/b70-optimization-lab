# Ornith 1.5 35B-A3B: accepted eleven-stack decode profile

Date: 2026-08-23 EDT

Status: **diagnostic ranking only — not throughput evidence**

Ornith 1.5 is Qwen-derived, so the Qwen 3.x optimization archive remains a
useful hypothesis library. The previous Ornith operation profile covered only
seven accepted features, however, and became stale after the GDN state-I/O,
GDN RMS/gate, shared-MoE residual/RMS, and full-attention Q/K
normalization-plus-RoPE wins. This run refreshes the ranking on the complete
accepted eleven-feature stack before selecting another transfer candidate.

The temporary profiler places queue barriers around every logical SYCL graph
loop iteration and measures host elapsed time. It deliberately serializes the
graph, includes dispatch and barrier overhead, and can charge a deferred or
fused graph match to the logical node where the matcher fires. These values
rank boundaries only. They must not be converted into a projected speedup or
compared with production token rates.

Seven graph submissions were captured. The final two were warmed one-token
graphs with 1,103 timed logical rows; the final graph is the structured
ranking source. Its largest operation families were:

| Logical operation family | Serialized diagnostic time |
| --- | ---: |
| `MUL_MAT` | 5584.920 µs |
| `MUL_MAT_ID` | 2113.271 µs |
| `ADD` | 1481.651 µs |
| `GET_ROWS` | 999.941 µs |
| `RMS_NORM` | 705.183 µs |
| `UNARY` | 659.311 µs |
| fused router top-k, attributed to `SOFT_MAX` | 520.177 µs |

The largest named projection boundaries were the already-fused routed
gate/up path (1171.193 µs), routed down (942.078 µs), recurrent QKV
(897.537 µs), router logits (717.631 µs), and the single output head
(707.522 µs). The 40 router-top-k calls were already handled by llama.cpp's
fused MoE selector; their `SOFT_MAX` label is timer attribution, not evidence
of an unfused softmax chain.

This changes the next-candidate ordering but does not itself identify a win.
The old Qwen output-head/top-1 shortcut was separately closed because
`ARGMAX` never enters the SYCL graph. The routed down/weighted-reduction and
shared-Q8 projection variants have also already failed exactness or matched
performance gates. The remaining Qwen-derived MoE router/gate boundary is
worth inspecting, but any replacement for the current FP32 router projection
must first reproduce its reduction behavior exactly; the direct oneMKL GEMV
attempt already changed generation.

The default-off profiler is archived at
`../patches/llamacpp-ornith15-eleven-stack-op-profiler-diagnostic-20260823.patch`.
The compressed raw log, CLI transcript, and structured ranking are adjacent
under `../data/`. After capture, the complete source diff and all four
published binaries were restored byte-exact to the accepted package.

## Follow-up correction

A later execution-counter audit confirmed that the 120 convolution-state and
120 GDN-state generic gathers belong to prompt/setup graphs. In the 127-token
decode interval, the accepted direct concat/state and in-place GDN state paths
each fired all 3,810 expected times, leaving no generic recurrent state gather
in one-token decode. The large serialized `GET_ROWS` family value above is
therefore deferred-work attribution, not a count or cost of recurrent decode
gathers. The actual remaining one-token `result_norm` gather was bypassed by an
exact Q6_K output-head candidate, but the matched engine moved only +0.0415%,
so it was closed neutral. See
`2026-08-23-ornith35b-final-getrows-direct-neutral.md`.
