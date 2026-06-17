# Qwen3.6 Spec Trace Summary

## Trace: `/home/steve/llm-optimizations/data/qwen36-oracle1-serialgdn-eager-paired-20260615g11-spec-trace.jsonl`

- rows `16`, requests `2`, drafts `16`, accepted `13`, rejected `3`, accept rate `81.25%`
- full accept rows `13` (`81.25%`), full reject rows `3` (`18.75%`)
- suppressed bonus rows `0` (`0.00%`)
- max full-accept streak `5`
- repeated scheduled rows `0`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-ab7be22d838d79fd-0-879a7125` | 12 | 10 | 2 | 83.33% | 5 |
| `cmpl-b778328a79aacaf2-0-bc09d75b` | 4 | 3 | 1 | 75.00% | 3 |

## Joinability

- exact request-id join possible: `False`
- exact request-id matches: `0`
- prefix request-id matches: `0`
- timestamp-window join possible: `False`
- note: Artifacts do not store request ids. Re-run metrics with current scripts before attributing trace rows to exact prompts.

