# Qwen3.6 Spec Trace Summary

## Trace: `/home/steve/llm-optimizations/data/qwen36-eagle2-corpus2-k1-smoke-20260618a-spec.jsonl`

- rows `203`, requests `3`, drafts `203`, accepted `85`, rejected `118`, accept rate `41.87%`
- full accept rows `85` (`41.87%`), full reject rows `118` (`58.13%`)
- suppressed bonus rows `0` (`0.00%`)
- max full-accept streak `13`
- repeated scheduled rows `0`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-950b4e7ba18eb0b0-0-9781ec80` | 90 | 38 | 52 | 42.22% | 13 |
| `cmpl-a43cabe2c531f1aa-0-a6c26fba` | 90 | 38 | 52 | 42.22% | 13 |
| `cmpl-9961e801bbe54f8f-0-b7f4f8e1` | 23 | 9 | 14 | 39.13% | 6 |

## Metric Artifacts

| label | preset | corrected tok/s | output tokens | request IDs | timestamps |
| --- | --- | ---: | --- | --- | --- |
| `qwen36-ablation-eagle2-corpus2-fastpath-piecewise-tp2-k1-smoke-20260618a-p512o512-20260618112000` | `natural-chat` | 54.87 | [128, 128] | True | True |

## Joinability

- exact request-id join possible: `True`
- exact request-id matches: `0`
- prefix request-id matches: `2`
- timestamp-window join possible: `True`
- note: Trace rows can be joined to artifacts by request-id prefix; scheduler ids append an internal suffix.
