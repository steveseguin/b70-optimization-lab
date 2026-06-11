# Qwen3.6 Spec Trace Summary

## Trace: `data/qwen36-quark-int8-tp4-ngram5-nobonus-state-spec-jsonl-20260611.jsonl`

- rows `4`, requests `3`, drafts `20`, accepted `10`, rejected `10`, accept rate `50.00%`
- full accept rows `2` (`50.00%`), full reject rows `2` (`50.00%`)
- suppressed bonus rows `2` (`50.00%`)
- max full-accept streak `1`
- repeated scheduled rows `0`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `chatcmpl-910ade65c5503c90-a467094e` | 10 | 5 | 5 | 50.00% | 1 |
| `chatcmpl-ace7501683203c95-8b54df50` | 5 | 5 | 0 | 100.00% | 1 |
| `chatcmpl-95cc14d95464d068-bca29e44` | 5 | 0 | 5 | 0.00% | 0 |

## Quality Artifacts

| label | pass all | baseline match | repeat pass | repeat unique hashes | long context |
| --- | --- | --- | --- | ---: | --- |
| `state` | None | False | None | None | None |

## Joinability

- exact request-id join possible: `False`
- timestamp-window join possible: `False`
- note: Metric artifacts do not store request ids. Re-run prompt-class metrics with the current benchmark script before attributing trace rows to exact prompts.
