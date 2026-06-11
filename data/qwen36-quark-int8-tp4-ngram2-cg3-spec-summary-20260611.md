# Qwen3.6 Spec Trace Summary

## Trace: `data/qwen36-quark-int8-tp4-ngram2-cg3-spec-jsonl-20260611.jsonl`

- rows `685`, requests `14`, drafts `1365`, accepted `1044`, rejected `321`, accept rate `76.48%`
- full accept rows `477` (`69.64%`), full reject rows `116` (`16.93%`)
- suppressed bonus rows `0` (`0.00%`)
- max full-accept streak `147`
- repeated scheduled rows `53`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-a42f7ab62e347506-0-b329a4e1` | 315 | 312 | 3 | 99.05% | 147 |
| `cmpl-9d168d0201a614d1-0-a1ce1bbf` | 262 | 228 | 34 | 87.02% | 89 |
| `cmpl-9ea8e35a81e0b947-0-87cba57c` | 213 | 163 | 50 | 76.53% | 55 |
| `cmpl-9823f28986436f3e-0-85986885` | 186 | 118 | 68 | 63.44% | 26 |
| `cmpl-8552284b4b7432ca-0-890d62d4` | 174 | 101 | 73 | 58.05% | 20 |

## Trace: `data/qwen36-quark-int8-tp4-ngram2-cg3-chat-promptclass-spec-jsonl-20260611.jsonl`

- rows `668`, requests `12`, drafts `1334`, accepted `617`, rejected `717`, accept rate `46.25%`
- full accept rows `245` (`36.68%`), full reject rows `296` (`44.31%`)
- suppressed bonus rows `0` (`0.00%`)
- max full-accept streak `8`
- repeated scheduled rows `14`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `chatcmpl-92cc2eb829d121f6-ab3f82b2` | 242 | 169 | 73 | 69.83% | 8 |
| `chatcmpl-ae99475ff9cd7d8c-b34c9cfd` | 242 | 169 | 73 | 69.83% | 8 |
| `chatcmpl-b581b5fff4a30949-863593c5` | 201 | 74 | 127 | 36.82% | 4 |
| `chatcmpl-8bba5cf76f016eff-9c1da4f6` | 192 | 99 | 93 | 51.56% | 8 |
| `chatcmpl-918e868f80435029-958aa37c` | 124 | 33 | 91 | 26.61% | 1 |

## Trace: `data/qwen36-quark-int8-tp4-ngram2-cg3-chat-promptclass-seeded-spec-jsonl-20260611.jsonl`

- rows `662`, requests `12`, drafts `1321`, accepted `609`, rejected `712`, accept rate `46.10%`
- full accept rows `238` (`35.95%`), full reject rows `291` (`43.96%`)
- suppressed bonus rows `0` (`0.00%`)
- max full-accept streak `8`
- repeated scheduled rows `10`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `chatcmpl-835c4705dc1b49b7-84bde707` | 246 | 168 | 78 | 68.29% | 8 |
| `chatcmpl-89ba206135f84fe0-8f2226c1` | 242 | 169 | 73 | 69.83% | 8 |
| `chatcmpl-9a2f3041f12c25d4-8149770b` | 184 | 79 | 105 | 42.93% | 4 |
| `chatcmpl-85b9e8ee7731feae-8e39b97d` | 165 | 80 | 85 | 48.48% | 4 |
| `chatcmpl-ae33a5bf9ef885af-99d51902` | 135 | 46 | 89 | 34.07% | 2 |

## Metric Artifacts

| label | preset | corrected tok/s | output tokens | request IDs | timestamps |
| --- | --- | ---: | --- | --- | --- |
| `accepted-natural-chat` | `natural-chat` | 99.59 | [512, 512] | False | False |
| `ngram2-natural-chat` | `natural-chat` | 90.85 | [512, 512] | False | False |
| `accepted-code` | `code` | 99.61 | [512, 512] | False | False |
| `ngram2-code` | `code` | 93.73 | [512, 512] | False | False |
| `accepted-structured` | `structured` | 99.44 | [512, 512] | False | False |
| `ngram2-structured` | `structured` | 116.36 | [440, 445] | False | False |
| `accepted-math-reasoning` | `math-reasoning` | 99.40 | [512, 512] | False | False |
| `ngram2-math-reasoning` | `math-reasoning` | 98.39 | [512, 512] | False | False |

## Metric Comparisons

| candidate | baseline | delta | same output-token counts |
| --- | --- | ---: | --- |
| `ngram2-natural-chat` | `accepted-natural-chat` | -8.77% | True |
| `ngram2-code` | `accepted-code` | -5.91% | True |
| `ngram2-structured` | `accepted-structured` | +17.01% | False |
| `ngram2-math-reasoning` | `accepted-math-reasoning` | -1.02% | True |

## Quality Artifacts

| label | pass all | baseline match | repeat pass | repeat unique hashes | long context |
| --- | --- | --- | --- | ---: | --- |
| `ngram2-rerun64` | True | True | True | ['c40708bd7280e02bd9dc04ec775023d5be7b4870ea8096039af38576e60fc80b'] | True |

## Joinability

- exact request-id join possible: `False`
- timestamp-window join possible: `False`
- note: Metric artifacts do not store request ids. Re-run prompt-class metrics with the current benchmark script before attributing trace rows to exact prompts.

