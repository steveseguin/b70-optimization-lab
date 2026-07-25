# Laguna S 2.1 persistent exact-attention metadata record candidate

Date: 2026-07-25 America/Toronto

Status: **VERIFIED, INDEPENDENTLY AUDITED, READY TO SUBMIT**. The conservative
lower candidate start is `94.92003934159611 tok/s`, compared with approved
record `cmrzjb7i906x4o401egrnm05m` at `92.16352215694299 tok/s`.

## Result

The preregistered fresh-service graph-vs-graph A1/B1/B2/A2 campaign passed
every quality, honesty, causal, reproducibility, practical-floor, and record
gate:

| Leg | Treatment | Median tok/s, tokens 1-100 after TTFT | Canonical exact | Cached tokens |
|---|---|---:|---:|---:|
| A1 | graph, metadata off | 92.54961760665958 | 13/13 | 0 on 13/13 |
| B1 | graph, metadata on | **94.92003934159611** | 13/13 | 0 on 13/13 |
| B2 | graph, metadata on | 95.06654837534518 | 13/13 | 0 on 13/13 |
| A2 | graph, metadata off | 92.87797142677606 | 13/13 | 0 on 13/13 |

The eligible value is the lower B start. It improves the prior approved record
by `2.75651718465312 tok/s` (`+2.990898264455555%`) and strictly exceeds the
preregistered `92.393930962335 tok/s` practical floor.

Both adjacent comparisons passed:

| Pair | Candidate row wins | Headline gain | Median paired gain | Cycle saving | Acceptance drift |
|---|---:|---:|---:|---:|---:|
| B1 vs A1 | 13/13 | +2.5612442236238477% | +2.3511088081138385% | 0.9112340643584034 ms | 0.0003077489561834623 |
| B2 vs A2 | 13/13 | +2.3564004628315667% | +2.5609196498322975% | 1.6476436413154687 ms | 0.0003070338847266929 |

All 52 leg outputs match the canonical q1 greedy teacher bitwise. The cross-leg
bundle is 39/39 exact, every cached-token count is zero, and long-then-next and
the 863-token rollover row pass on every leg. Metrics began at zero and each
fresh service handled exactly 13 unique prompts once.

## What changed

All four starts use the approved exact DFlash7, fused W1-route-W2,
route-interleaved expert GEMM, shared-elementwise, QKNorm/RoPE, W1 N64, and
Breakable PIECEWISE graph stack. The sole treatment difference is:

```text
A control: VLLM_XPU_LAGUNA_M8_PREBUILT_EXACT_ATTN_METADATA=0
B candidate: VLLM_XPU_LAGUNA_M8_PREBUILT_EXACT_ATTN_METADATA=1
```

The candidate moves exact q2..q8 attention metadata into builder-owned,
fixed-address XPU buffers. Query offsets, growing KV lengths, and expanded
block tables are refreshed in place on the current stream. Metadata object,
base pointer, offset, active-view, and owner signatures are guarded and fail
closed on drift. `VLLM_XPU_LAGUNA_M8_CAPTURE_ATTENTION_GRAPHS=0` throughout;
the attention kernels remain eager boundaries inside the same 146-graph,
145-boundary topology.

Every start performed its first lazy graph capture inside the first measured
cold request and logged one audited capture and replay on ranks 0 through 3.
There was no warm-up generation, retry, prefix cache, history/ngram
acceleration, response reuse, context checkpoint, qualification timing, or
prior-run output.

## Frozen identity

- main formal tooling:
  `ea70d34fee12719889db8e23cb4e18f19d1e9555`;
- vLLM:
  `ef334233deabeaeedb607056a2db1c90edb3887c`;
- XPU kernels:
  `4772f727590c51b72add79350b913d098cf67872`;
- target revision:
  `4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb`;
- DFlash revision:
  `5e07c246915c86dc6920fead03d019989224f2ba`; and
- hardware: four Intel Arc Pro B70, TP4/EP4, one active generation.

Models, private cache/RPC roots, and evidence all used internal EXT4 NVMe.

## Sealed evidence

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-metadata-formal-ea70d34fe-ef334233d-20260725T015736Z
```

Key SHA256:

```text
1f4334ccdf45e3c17e68366c4e24ff95adc022809d60986146c10d00cdd460f9  full-analysis.json
6b4c1aebfdc7bcd5779d640e4276f9dec33abcc54d3a8b958c8f19f443d7e332  all-vs-teacher.json
1a3a85587d2409a5ee04740ce78504796766baecbc5e2e0036eda751e0be2fa9  cross-leg.json
5d7e9e49faac7046fdff4a6d83dc8ea7b4c6990ebb67d76d50cb42e98fdde6e2  B1-graph-metadata-on/bench.json
04e18dde23f53ebf9eeee0a3760bf7daeb3d0a20bc1f119fa2f43bc013bdde56  B1-graph-metadata-on/exactness-vs-q1.json
3f26de97073a3283b50c7b762e8124c70434308be96faaa035bf52bdc64b85ac  B1-graph-metadata-on/server.log
```

The committed analyzer emitted `record_candidate`. A separate read-only agent
recomputed source/tool identities, all four leg gates, 52/52 canonical
exactness, 39/39 cross-leg exactness, raw performance statistics, paired
metrics, topology, idle intervals, cleanup, sealing, treatment isolation, and
absence of retry/rescue roots, then approved submission of the lower B start.

For a read-only analyzer rerun, use the repository root as the current working
directory. The controller recorded its self-path relative to that intended
launch directory; this is a rerun hardening issue, not an evidence discrepancy
in the sealed campaign.

## Decision

Submit only `94.92003934159611 tok/s`, never the faster B2 value. Preserve all
four starts as the reproducibility record.
