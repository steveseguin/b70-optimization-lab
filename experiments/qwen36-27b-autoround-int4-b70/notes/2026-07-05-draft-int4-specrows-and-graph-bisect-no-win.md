# 2026-07-05: draft INT4 spec-row and graph bisection no-win

Objective: continue trying to beat the current valid one-B70 Qwen27 record
`65.27648650325429 tok/s` for
`webhie/Qwen3.6-27B-int4-AutoRound + runtime INT8 LM-head BF16 scales`
without lowering quality or using cached/history effects.

Current valid record remains unchanged:

- result packet:
  `results/qwen36-27b-autoround-int4-b70/webhie-int8-lmhead-bf16scale-20260703.json`;
- LocalMaxxing id: `cmr5iu3gk00bfq901nidgcana`;
- policy: fixed realistic suite, each prompt once, `cached_tokens=0`, median
  tokens 1-100 after TTFT, plus repeat/quality validation.

## Patch snapshot

Patch artifact:

```text
patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-keep-scheduled-spec-rows-no-win-20260705.patch
```

The patch added a default-off
`VLLM_XPU_GDN_KEEP_SCHEDULED_SPEC_ROWS=1` mode in
`vllm/v1/attention/backends/gdn_attn.py`. It forced every scheduler-marked
spec row to stay on the GDN spec path, reusing the ReplaySSM routing behavior
without enabling ReplaySSM rings/replay.

Why tried: normal non-ReplaySSM GDN demotes scheduled spec rows to non-spec when
`num_accepted_tokens <= 1`, while ReplaySSM keeps scheduled rows on the spec
path. Since ReplaySSM is correct but slow, this was a minimal test of whether
the fast path only needed the same row routing.

Result: no-win. The live source hook was reverted after testing, but the patch
artifact is preserved so future agents do not repeat the idea.

## Same-window keep-spec-rows screen

All rows used:

- `webhie/Qwen3.6-27B-int4-AutoRound`;
- runtime target INT8 LM-head, BF16 scales;
- draft INT4 / separate draft head path;
- MTP3, strict fresh realistic suite, each prompt once, `cached_tokens=0`;
- repeat64 Qwen quality screen.

| Label | Median tok/s | p10 | TTFT median | Strict fresh gate | Quality |
| --- | ---: | ---: | ---: | --- | --- |
| `qwen27-targetint8-draftint4-keepspecrows-gpu0` | `70.638286` | `63.866030` | `489.5 ms` | pass, cached-zero | fail repeat64 |
| `qwen27-targetint8-draftint4-keepspecrows-alignrestore-gpu1` | `71.995315` | `65.145767` | `493.0 ms` | pass, cached-zero | fail repeat64 |
| `qwen27-targetint8-draftint4-keepspecrows-noasync-gpu2` | `68.002443` | `61.162522` | `451.3 ms` | pass, cached-zero | fail repeat64 |

All three quality failures had the same repeat64 split:

```text
blue, green, red, yellow: 55/64
blue, green, red:          9/64
```

Artifacts:

```text
data/qwen36-27b-autoround-int4-b70-baselines/keep-specrows-screen-20260705T162228Z/qwen27-targetint8-draftint4-keepspecrows-gpu0-candidate-summary-20260705T162228Z.json
data/qwen36-27b-autoround-int4-b70-baselines/keep-specrows-screen-20260705T162228Z/qwen27-targetint8-draftint4-keepspecrows-alignrestore-gpu1-candidate-summary-20260705T162228Z.json
data/qwen36-27b-autoround-int4-b70-baselines/keep-specrows-screen-20260705T162229Z/qwen27-targetint8-draftint4-keepspecrows-noasync-gpu2-candidate-summary-20260705T162229Z.json
```

## Graph / async bisection

The next screen tested whether the remaining draft-INT4 failure was only XPU
graph capture or async scheduling. It was not.

| Label | Median tok/s | p10 | TTFT median | Strict fresh gate | Quality |
| --- | ---: | ---: | ---: | --- | --- |
| `qwen27-targetint8-draftint4-graphoff-async-gpu0` | `62.389146` | `58.573542` | `496.6 ms` | pass, cached-zero | fail repeat64 |
| `qwen27-targetint8-draftint4-graphoff-noasync-gpu1` | `60.590691` | `54.121012` | `459.4 ms` | pass, cached-zero | fail repeat64 |
| `qwen27-targetint8-draftint4-cg4-gpu2` | `72.160912` | `65.239129` | `490.4 ms` | pass, cached-zero | fail repeat64 |
| `qwen27-targetint8-draftint4-cg4-alignrestore-gpu3` | `71.908525` | `64.838580` | `494.7 ms` | pass, cached-zero | fail repeat64 |

Every row again had the identical repeat64 split:

```text
blue, green, red, yellow: 55/64
blue, green, red:          9/64
```

Artifacts:

```text
data/qwen36-27b-autoround-int4-b70-baselines/draftint4-graph-bisect-20260705T162714Z/qwen27-targetint8-draftint4-graphoff-async-gpu0-candidate-summary-20260705T162714Z.json
data/qwen36-27b-autoround-int4-b70-baselines/draftint4-graph-bisect-20260705T162714Z/qwen27-targetint8-draftint4-graphoff-noasync-gpu1-candidate-summary-20260705T162714Z.json
data/qwen36-27b-autoround-int4-b70-baselines/draftint4-graph-bisect-20260705T162714Z/qwen27-targetint8-draftint4-cg4-gpu2-candidate-summary-20260705T162714Z.json
data/qwen36-27b-autoround-int4-b70-baselines/draftint4-graph-bisect-20260705T162714Z/qwen27-targetint8-draftint4-cg4-alignrestore-gpu3-candidate-summary-20260705T162714Z.json
```

## Interpretation

The fast draft-INT4 rows are tempting because they reach `68-72 tok/s`, but
they are invalid. They are strict fresh-response runs with `cached_tokens=0`,
so this is not a benchmark-cheating issue. It is a quality/state-transaction
issue.

These screens rule out several cheap explanations:

- not only `accepted_count == 1` row demotion: keeping scheduler spec rows on
  the spec path still fails;
- not only XPU graph capture: graph-off rows still fail;
- not only async scheduling: graph-off/no-async still fails;
- not fixed by align+partial/full-accept restore in the normal fast path.

ReplaySSM+align remains the only draft-INT4 path in this family that has been
shown quality-clean, but it is below the current record (`61-62 tok/s` versus
`65.276 tok/s`).

## Conclusion

No LocalMaxxing submission. No new valid record.

Do not spend more endpoint time on keep-spec-row routing, graph-off/no-async
bisections, or normal align/restore knobs for this draft-INT4 lane. The next
credible work is source-level: profile and reduce ReplaySSM/full-accept state
transaction cost, or design a cheaper exact GDN state tape/replay that keeps
the `blue, green, red, yellow` repeat stable without the current ReplaySSM
overhead.
