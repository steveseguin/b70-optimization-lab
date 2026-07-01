# Qwen3.6 Spec Trace Summary

## Trace: `/home/steve/llm-optimizations/data/qwen36-eagle1-smoke-trained-nopreempt-tp2-20260618a-spec-trace.jsonl`

- rows `94`, requests `2`, drafts `94`, accepted `4`, rejected `90`, accept rate `4.26%`
- full accept rows `4` (`4.26%`), full reject rows `90` (`95.74%`)
- suppressed bonus rows `0` (`0.00%`)
- max full-accept streak `1`
- repeated scheduled rows `0`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-9319c64870738adb-0-9df672f5` | 63 | 2 | 61 | 3.17% | 1 |
| `cmpl-906b14a97108287a-0-a11f98b9` | 31 | 2 | 29 | 6.45% | 1 |

## Metric Artifacts

| label | preset | corrected tok/s | output tokens | request IDs | timestamps |
| --- | --- | ---: | --- | --- | --- |
| `qwen36-eagle1-smoke-trained-nopreempt-naturalchat-tp2-20260618a-measure` | `natural-chat` | 6.87 | [64] | True | True |

## Joinability

- exact request-id join possible: `True`
- exact request-id matches: `0`
- prefix request-id matches: `1`
- timestamp-window join possible: `True`
- note: Trace rows can be joined to artifacts by request-id prefix; scheduler ids append an internal suffix.
