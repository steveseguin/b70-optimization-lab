# Qwen3.6 Spec Trace Summary

## Trace: `data/qwen36-oracle1-paired-freshgraph-20260615g5-spec-trace.jsonl`

- rows `14`, requests `2`, drafts `14`, accepted `13`, rejected `1`, accept rate `92.86%`
- full accept rows `13` (`92.86%`), full reject rows `1` (`7.14%`)
- suppressed bonus rows `0` (`0.00%`)
- max full-accept streak `8`
- repeated scheduled rows `0`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-b96876a2f0994db7-0-a6a5a8f1` | 9 | 8 | 1 | 88.89% | 8 |
| `cmpl-9fe9fa7abd170bce-0-93fc9484` | 5 | 5 | 0 | 100.00% | 5 |

## Quality Artifacts

| label | pass all | baseline match | repeat pass | repeat unique hashes | long context |
| --- | --- | --- | --- | ---: | --- |
| `candidate` | None | False | None | None | None |

## Joinability

- exact request-id join possible: `True`
- exact request-id matches: `0`
- prefix request-id matches: `2`
- timestamp-window join possible: `True`
- note: Trace rows can be joined to artifacts by request-id prefix; scheduler ids append an internal suffix.
