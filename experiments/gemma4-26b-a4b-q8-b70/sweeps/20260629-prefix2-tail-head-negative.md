# 2026-06-29 Prefix2 Tail-Head Verifier Experiment

Status: **closed negative**. Valid fresh-response screens passed quality, but
the new verifier shape was slower than paired controls and stayed below the
current `115.8466634928202 tok/s` Gemma Q8 record.

## Idea

The current `n_max=3` MTP verifier path pays for target/verifier output rows
for the sampled token, draft rows, and bonus row. The experiment tried to reduce
the full target LM-head/verifier work by:

- outputting only the first two verifier rows in the main target decode;
- if those prefix rows matched, running a dedicated batched `SPEC_HEAD` pass
  over saved `h_nextn` rows for the third draft token plus bonus token;
- preserving exact target verification semantics for every accepted token.

Default-off flags:

```text
LLAMA_SPEC_VERIFY_PREFIX2_TAIL_HEAD=1
LLAMA_SPEC_HEAD_FUSED_OUTPUT_ARGMAX=1
```

The implementation added a batched `SPEC_HEAD` API:
`llama_spec_verify_head_from_h_nextn_range(...)`, plus server-side prefix/tail
acceptance plumbing for the `n_max=3` shape.

## Validity

All four lanes used the fixed realistic cold suite:

- each prompt sent once;
- `cached_tokens=0` on every request;
- no prompt/KV/cache/history/ngram reuse;
- UD-Q8_K_XL target/verifier, Q4_0 MTP draft;
- target-verified speculative acceptance;
- `128/128` chat canary rows passed.

These were strict128 screens, so they are diagnostic only. Full512 would still
be required before any promotion, but the screen was already a clear loss.

## Results

| Lane | Summary | Median 1-100 | p10 | Mean | Full128 after TTFT | Wall full128 | TTFT |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| GPU0 control | `data/gemma4-q8-gpu0-prefix2-control-strict128-20260629Tscreen/summary.json` | 113.06087929593555 | 101.18287432904049 | 112.79059918600707 | 111.71788060020847 | 96.84111890724242 | 176.976 ms |
| GPU2 control | `data/gemma4-q8-gpu2-prefix2-control-strict128-20260629Tscreen/summary.json` | 109.84126678960445 | 105.05576977507168 | 113.5955432397458 | 113.47535137448804 | 97.78156226444416 | 177.108 ms |
| GPU1 prefix2 tail-head | `data/gemma4-q8-gpu1-prefix2-tailhead-strict128-20260629Tscreen/summary.json` | 106.39578905120092 | 97.94138415859153 | 107.82780067685393 | 106.21011037942046 | 91.9785867032935 | 177.072 ms |
| GPU3 prefix2 tail-head + profile | `data/gemma4-q8-gpu3-prefix2-tailhead-profile-strict128-20260629Tscreen/summary.json` | 100.89727533814579 | 96.88712349600755 | 103.57193978106278 | 104.04090145570095 | 90.5674060500616 | 178.282 ms |

Profiled server log:

```text
/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu3-prefix2-tailhead-profile-strict128-20260629Tscreen.server.log
```

Key profile line at the end of the run:

```text
prefix2_tail head_ms=1762.285 calls=649 tail_tokens=1298 prefix_matches=649 avg=2.715 ms
```

Interpretation: the prefix rows almost always matched, so the added batched
`SPEC_HEAD` pass ran on nearly every generation step. Its `2.715 ms/call`
overhead outweighed any savings from reducing rows in the main verifier graph.
The path was therefore a net loss even before accounting for profiling overhead.

## Decision

Do not promote, submit, or full512-confirm this implementation. Keep it
default-off as a reference for future verifier-shape work.

The negative result does **not** invalidate the broader goal of reducing
verifier cost. It specifically closes the current "two-row prefix then two-row
SPEC_HEAD tail" shape. A future exact verifier design needs to avoid launching
an extra full-vocab head pass on almost every step, or make that pass much
cheaper than the rows it removes.

## Artifacts

- Source snapshot:
  `patches/gemma4-26b-a4b-q8-b70/20260629-prefix2-tail-head-cumulative-source.patch.gz.b64`
  (`sha256=449010c61a71f951f8d6f15616d00327ce3a238a867687c3e4a3e344798b87fd`
  for the encoded artifact; raw patch checksum before gzip/base64 was
  `e58e1c3306b3179853bfc42fc7419990a468c3b444850de6ad55fc1370e9a007`).
- Harness patch:
  `patches/gemma4-26b-a4b-q8-b70/20260629-prefix2-tail-head-harness.patch`
  (`sha256=2732ea93140773a430bb24a382b3a3de44ae36dc21d31ae74fffa1079a826c24`).

The source snapshot is cumulative against upstream llama.cpp `c926ad098`
because `/home/steve/src/llama.cpp-gemma-record-repro-c926` already contains
the broader Gemma record stack and default-off experiment code. Treat it as a
recovery/audit snapshot, not as a minimal upstream patch.

## Follow-Up

Prefer these next lanes over more tuning of this shape:

- exact regular-Q8 LM-head candidate-vs-max or compact max that does not use
  the slower `MUL_MAT_ARGMAX` family;
- MoE boundary/kernel reduction that avoids extra graph launches;
- a true row-adaptive verifier path that avoids a second head pass on common
  full-prefix matches.
