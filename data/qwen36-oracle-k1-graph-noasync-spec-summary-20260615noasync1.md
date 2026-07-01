# Qwen3.6 Spec Trace Summary

## Trace: `/home/steve/llm-optimizations/data/qwen36-oracle-k1-graph-noasync-20260615a-spec.jsonl`

- rows `16`, requests `2`, drafts `16`, accepted `15`, rejected `1`, accept rate `93.75%`
- full accept rows `15` (`93.75%`), full reject rows `1` (`6.25%`)
- suppressed bonus rows `0` (`0.00%`)
- max full-accept streak `8`
- repeated scheduled rows `0`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-qwen36-oracle-k1-graph-noasync-20260615a-000000-0-8f1c9116` | 9 | 8 | 1 | 88.89% | 8 |
| `cmpl-qwen36-oracle-k1-graph-noasync-20260615a-000001-0-b3896e3a` | 7 | 7 | 0 | 100.00% | 7 |

## Quality Artifacts

| label | pass all | baseline match | repeat pass | repeat unique hashes | long context |
| --- | --- | --- | --- | ---: | --- |
| `noasync` | None | False | None | None | None |

## Joinability

- exact request-id join possible: `True`
- exact request-id matches: `0`
- prefix request-id matches: `2`
- timestamp-window join possible: `True`
- note: Trace rows can be joined to artifacts by request-id prefix; scheduler ids append an internal suffix.
