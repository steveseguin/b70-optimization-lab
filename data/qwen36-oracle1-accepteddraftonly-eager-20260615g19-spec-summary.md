# Qwen3.6 Spec Trace Summary

## Trace: `data/qwen36-oracle1-accepteddraftonly-eager-20260615g19-spec-trace.jsonl`

- rows `6`, requests `2`, drafts `6`, accepted `4`, rejected `2`, accept rate `66.67%`
- full accept rows `4` (`66.67%`), full reject rows `2` (`33.33%`)
- suppressed bonus rows `0` (`0.00%`)
- max full-accept streak `3`
- repeated scheduled rows `0`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-ae973574abfa3739-0-a586f7b6` | 4 | 3 | 1 | 75.00% | 3 |
| `cmpl-b8cf4d7894c62595-0-be8478d9` | 2 | 1 | 1 | 50.00% | 1 |

## Joinability

- exact request-id join possible: `False`
- exact request-id matches: `0`
- prefix request-id matches: `0`
- timestamp-window join possible: `False`
- note: Artifacts do not store request ids. Re-run metrics with current scripts before attributing trace rows to exact prompts.
