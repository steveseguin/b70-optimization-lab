# Qwen3.8 Q4_K_M + Q4_0 MTP2 mixed-content depth result

Status: **passed; six Grade-B context/TTFT cells**.

The frozen campaign measured exact 2K, 4K, 8K, 16K, 24K, and 32K native HTTP
continuations over three unrepeated repository content classes: technical
prose, Python code, and structured documentation. One fresh MTP0 server froze
the per-case target oracle; two fresh MTP2 servers then ran the same 18 cases.
All 54 requests passed exact prompt-depth, cache-zero, no-truncation,
no-context-shift, 128-token, length-stop, and 100-event/99-interval gates.
Both before/after canary batteries passed on all three servers. All **36/36**
MTP2 output arrays exactly matched the MTP0 oracle.

| exact input | MTP0 control | MTP2 decode | MTP2 TTFT | fresh-run range | gain vs control |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 2,048 | 27.156384 | **41.424653** | 2.084 s | 0.553% | +52.54% |
| 4,096 | 26.891746 | **41.710028** | 4.180 s | 0.094% | +55.10% |
| 8,192 | 26.506893 | **41.497569** | 8.570 s | 0.085% | +56.55% |
| 16,384 | 25.614968 | **34.654659** | 18.030 s | 0.027% | +35.29% |
| 24,576 | 24.889767 | **32.257230** | 28.348 s | 0.175% | +29.60% |
| 32,768 | 24.150388 | **36.505065** | 39.538 s | 0.067% | +51.16% |

Each MTP2 value is the median of the two fresh-server medians; each server
median spans all three content classes. The structured result retains both
server samples and every class sample. The non-monotonic decode shape is
measured and reflects content-dependent draft acceptance; no point is fitted,
smoothed, interpolated, or extrapolated.

Publication authority is limited to this exact Q4_K_M target + external Q4_0
MTP2, one-B70, graph-off, F16 target/draft-KV, one-slot profile. These are raw
document continuations representative of real content shapes, not a natural
retrieval/task suite and not a new short-context headline or LocalMaxxing row.
The older repeated-token fixture's reproducible 2K/token-23 divergence remains
valid evidence that target parity is workload-scoped rather than universal.

Evidence:

- [aggregate result](../data/2026-08-27-qwen38-q4km-q4mtp-tp1-mixed-content-depth-r1-result.json)
- [preregistration](../data/2026-08-27-qwen38-q4km-q4mtp-tp1-mixed-content-depth-r1-prereg.json)
- [oracle amendment](../data/2026-08-27-qwen38-q4km-q4mtp-tp1-mixed-content-depth-r1-mtp2-amendment.json)
- [frozen fixture](../../../data/qwen27-exact-depth/qwen38-bce40ca-mixed-content-depth-v1.json)
- [runner](../scripts/run-20260827-qwen38-q4km-q4mtp-tp1-mixed-content-depth-arm.sh)
- [read-only validator](../scripts/validate-20260827-qwen38-q4km-q4mtp-tp1-mixed-content-depth-r1.py)
