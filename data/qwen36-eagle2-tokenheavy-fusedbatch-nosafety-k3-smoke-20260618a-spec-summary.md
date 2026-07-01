# Qwen3.6 Spec Trace Summary

## Trace: `/home/steve/llm-optimizations/data/qwen36-eagle2-tokenheavy-fusedbatch-nosafety-k3-smoke-20260618a-spec.jsonl`

- rows `146`, requests `3`, drafts `438`, accepted `141`, rejected `297`, accept rate `32.19%`
- full accept rows `20` (`13.70%`), full reject rows `69` (`47.26%`)
- suppressed bonus rows `0` (`0.00%`)
- max full-accept streak `6`
- repeated scheduled rows `146`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-83ba99587ebc9922-0-acd9e469` | 207 | 58 | 149 | 28.02% | 6 |
| `cmpl-ba1225bc0e2f817f-0-ad4b5919` | 198 | 61 | 137 | 30.81% | 6 |
| `cmpl-ab285dfcde525a59-0-8ececdb5` | 33 | 22 | 11 | 66.67% | 2 |

## Metric Artifacts

| label | preset | corrected tok/s | output tokens | request IDs | timestamps |
| --- | --- | ---: | --- | --- | --- |
| `qwen36-ablation-eagle2-tokenheavy-fusedbatch-nosafety-fastpath-piecewise-tp2-k3-smoke-20260618a-p512o512-20260618113318` | `natural-chat` | 64.70 | [128, 128] | True | True |

## Joinability

- exact request-id join possible: `True`
- exact request-id matches: `0`
- prefix request-id matches: `2`
- timestamp-window join possible: `True`
- note: Trace rows can be joined to artifacts by request-id prefix; scheduler ids append an internal suffix.
