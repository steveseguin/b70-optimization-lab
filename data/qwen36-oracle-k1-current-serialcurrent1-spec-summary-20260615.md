# Qwen3.6 Spec Trace Summary

## Trace: `/home/steve/llm-optimizations/data/qwen36-oracle-k1-current-20260615serialcurrent1-spec.jsonl`

- rows `105`, requests `2`, drafts `105`, accepted `98`, rejected `7`, accept rate `93.33%`
- full accept rows `98` (`93.33%`), full reject rows `7` (`6.67%`)
- suppressed bonus rows `0` (`0.00%`)
- max full-accept streak `61`
- repeated scheduled rows `0`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-qwen36-oracle-k1-current-20260615serialcurrent1-000001-0-977ee644` | 61 | 61 | 0 | 100.00% | 61 |
| `cmpl-qwen36-oracle-k1-current-20260615serialcurrent1-000000-0-a564f8cc` | 44 | 37 | 7 | 84.09% | 14 |

## Joinability

- exact request-id join possible: `False`
- exact request-id matches: `0`
- prefix request-id matches: `0`
- timestamp-window join possible: `False`
- note: Artifacts do not store request ids. Re-run metrics with current scripts before attributing trace rows to exact prompts.

