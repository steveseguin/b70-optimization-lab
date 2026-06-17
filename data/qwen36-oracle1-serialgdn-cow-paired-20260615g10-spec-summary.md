# Qwen3.6 Spec Trace Summary

## Trace: `/home/steve/llm-optimizations/data/qwen36-oracle1-serialgdn-cow-paired-20260615g10-spec-trace.jsonl`

- rows `6`, requests `2`, drafts `6`, accepted `4`, rejected `2`, accept rate `66.67%`
- full accept rows `4` (`66.67%`), full reject rows `2` (`33.33%`)
- suppressed bonus rows `0` (`0.00%`)
- max full-accept streak `3`
- repeated scheduled rows `0`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-975f60d8a448fb1c-0-a44ae2d9` | 4 | 3 | 1 | 75.00% | 3 |
| `cmpl-a415a4dec2b1cf7f-0-83233257` | 2 | 1 | 1 | 50.00% | 1 |

## Joinability

- exact request-id join possible: `False`
- exact request-id matches: `0`
- prefix request-id matches: `0`
- timestamp-window join possible: `False`
- note: Artifacts do not store request ids. Re-run metrics with current scripts before attributing trace rows to exact prompts.

