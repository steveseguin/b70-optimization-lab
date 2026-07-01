# Qwen3.6 Spec Trace Summary

## Trace: `/home/steve/llm-optimizations/data/qwen36-eagle2-tokenheavy-eagerbatch-k1-smoke-20260618a-spec.jsonl`

- rows `285`, requests `3`, drafts `285`, accepted `105`, rejected `180`, accept rate `36.84%`
- full accept rows `105` (`36.84%`), full reject rows `180` (`63.16%`)
- suppressed bonus rows `105` (`36.84%`)
- max full-accept streak `51`
- repeated scheduled rows `0`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-8df821396239ea47-0-bdd129c7` | 127 | 70 | 57 | 55.12% | 51 |
| `cmpl-9864fda9208f931e-0-92a57b56` | 127 | 19 | 108 | 14.96% | 13 |
| `cmpl-b88e2088e0ef4d8b-0-a48bed08` | 31 | 16 | 15 | 51.61% | 13 |

## Metric Artifacts

| label | preset | corrected tok/s | output tokens | request IDs | timestamps |
| --- | --- | ---: | --- | --- | --- |
| `qwen36-ablation-eagle2-tokenheavy-eagerbatch-fastpath-piecewise-tp2-k1-smoke-20260618a-p512o512-20260618111223` | `natural-chat` | 0.85 | [128, 128] | True | True |

## Joinability

- exact request-id join possible: `True`
- exact request-id matches: `0`
- prefix request-id matches: `2`
- timestamp-window join possible: `True`
- note: Trace rows can be joined to artifacts by request-id prefix; scheduler ids append an internal suffix.
