# Qwen3.6 Spec Trace Summary

## Trace: `/tmp/qwen36-ngram2-bucket-timing-spec-trace-20260611r.jsonl`

- rows `71`, requests `4`, drafts `142`, accepted `112`, rejected `30`, accept rate `78.87%`
- full accept rows `50` (`70.42%`), full reject rows `9` (`12.68%`)
- suppressed bonus rows `0` (`0.00%`)
- max full-accept streak `22`
- repeated scheduled rows `0`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-82dc56e552d1c554-0-83c4d5ae` | 64 | 38 | 26 | 59.38% | 4 |
| `cmpl-b37c48f727ab0fc5-0-8b99f327` | 56 | 52 | 4 | 92.86% | 22 |
| `cmpl-aa80d9002825d1cd-0-b179fdca` | 20 | 20 | 0 | 100.00% | 10 |
| `cmpl-8483b92572644a20-0-bcc38dd6` | 2 | 2 | 0 | 100.00% | 1 |

## Metric Artifacts

| label | preset | corrected tok/s | output tokens | request IDs | timestamps |
| --- | --- | ---: | --- | --- | --- |
| `qwen36-quark-int8-tp4-ngram2-bucket-timing-natural-p512o160-20260611` | `natural-chat` | 81.16 | [160] | True | True |

## Joinability

- exact request-id join possible: `True`
- exact request-id matches: `0`
- prefix request-id matches: `1`
- timestamp-window join possible: `True`
- note: Trace rows can be joined to artifacts by request-id prefix; scheduler ids append an internal suffix.
