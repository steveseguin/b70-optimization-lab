# Qwen3.8 MTP5/M6 Q64xK32 integration-DSO requalification (r4) result

Date: 2026-08-22

Classification: **`q64k32-candidate-qualified-for-endpoint-campaign` — the
integration DSO (`979e91c1…`) is qualified on both GPUs.**

Preregistration:
[`2026-08-22-qwen38-mtp5-m6-fa-q64k32-abba-r4-prereg.md`](2026-08-22-qwen38-mtp5-m6-fa-q64k32-abba-r4-prereg.md).
Structured comparison:
[`../data/2026-08-22-qwen38-mtp5-m6-fa-q64k32-abba-r4-comparison.json`](../data/2026-08-22-qwen38-mtp5-m6-fa-q64k32-abba-r4-comparison.json).

All eight fresh A-B-B-A packets passed every correctness, mutation, marker,
and mapping gate (run exit 0, 16 immutable files, root aggregate
`6edf3c8f7263aede9d0a4764580b6580394b644d1564411806e19fb08924d875`). Paired
bootstrap savings reproduce the r3-qualified numbers within noise:

| KV | GPU2 central (us/call) | GPU3 central (us/call) | r3 reference |
|---:|---|---|---|
| 128 | `7.736` (saving) | `7.671` (saving) | 7.81 / 7.73 |
| 1300 | **`74.780`** | **`75.028`** | 74.68 / 74.96 |

The kernel bytes are unchanged from r3's candidate; only the dispatch table
grew to full coverage, and the timing agreement confirms the table change is
performance-neutral at the operator. The integration DSO is qualified for
the endpoint3 campaign, which reuses the endpoint2 driver design with the
r3 stage identities (`candidate_device_sha=979e91c1…`, candidate graph
manifest `0642e029…`) and fresh `endpoint3` labels.
