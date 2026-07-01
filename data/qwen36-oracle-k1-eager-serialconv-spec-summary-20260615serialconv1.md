# Qwen3.6 Spec Trace Summary

## Trace: `/home/steve/llm-optimizations/data/qwen36-oracle-k1-eager-serialconv-20260615a-spec.jsonl`

- rows `6`, requests `2`, drafts `6`, accepted `4`, rejected `2`, accept rate `66.67%`
- full accept rows `4` (`66.67%`), full reject rows `2` (`33.33%`)
- suppressed bonus rows `0` (`0.00%`)
- max full-accept streak `3`
- repeated scheduled rows `0`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-qwen36-oracle-k1-eager-serialconv-20260615a-000000-0-b2490ce8` | 4 | 3 | 1 | 75.00% | 3 |
| `cmpl-qwen36-oracle-k1-eager-serialconv-20260615a-000001-0-9e990a57` | 2 | 1 | 1 | 50.00% | 1 |

## Quality Artifacts

| label | pass all | baseline match | repeat pass | repeat unique hashes | long context |
| --- | --- | --- | --- | ---: | --- |
| `serialconv` | None | False | None | None | None |

## Joinability

- exact request-id join possible: `True`
- exact request-id matches: `0`
- prefix request-id matches: `2`
- timestamp-window join possible: `True`
- note: Trace rows can be joined to artifacts by request-id prefix; scheduler ids append an internal suffix.
