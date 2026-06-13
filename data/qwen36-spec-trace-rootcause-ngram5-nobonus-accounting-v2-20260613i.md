# Qwen3.6 Spec Trace Replay

- trace: `data/qwen36-quark-int8-tp4-ngram5-nobonus-accounting-spec-jsonl-20260611.jsonl`
- rows: `6`
- malformed rows: `0`
- requests: `3`
- suppressed follow-up mismatches: `1`
- suppressed schedule mismatches: `2`
- suppressed accept mismatches: `2`
- accounting mismatches: `0`

| request | rows | drafts | accepted | rejected | suppressed rows | joined token case | generated mismatches | schedule mismatches | accept mismatches | accounting mismatches |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| `chatcmpl-8d175ba4ed1de4c0-a690c281` | 4 | 20 | 14 | 6 | 2 | `` | 1 | 2 | 2 | 0 |
| `chatcmpl-9921ca8777ee6db5-a982c57e` | 1 | 5 | 5 | 0 | 1 | `` | 0 | 0 | 0 | 0 |
| `chatcmpl-ba141f1fd8db6894-815e0bf2` | 1 | 5 | 0 | 5 | 0 | `` | 0 | 0 | 0 | 0 |

## Suppressed Follow-Up Mismatches

- request `chatcmpl-8d175ba4ed1de4c0-a690c281` line `5` -> `6`:
  suppressed `21` `None`, next scheduled `15` `None`, next verifier token was `15` `None`, next emitted `15` `None`.

## Request Counter Transitions

| request | line | scheduled | accepted | rejected | computed delta | output-token delta | token delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `chatcmpl-8d175ba4ed1de4c0-a690c281` | 3 | 6 | 5 | 0 | -1 | 5 | 5 |
| `chatcmpl-8d175ba4ed1de4c0-a690c281` | 4 | 6 | 0 | 5 | -5 | 1 | 1 |
| `chatcmpl-8d175ba4ed1de4c0-a690c281` | 5 | 6 | 5 | 0 | -1 | 5 | 5 |
| `chatcmpl-8d175ba4ed1de4c0-a690c281` | 6 | 6 | 4 | 1 | -1 | 5 | 5 |
| `chatcmpl-9921ca8777ee6db5-a982c57e` | 1 | 6 | 5 | 0 | -1 | 4 | 4 |
| `chatcmpl-ba141f1fd8db6894-815e0bf2` | 2 | 6 | 0 | 5 | -5 | 1 | 1 |

Post-output `computed_minus_tokens` is included in the JSON rows.
Values below zero usually mean the next pass may recompute an already
emitted token; values above zero after suppressing a bonus can mean stale
unemitted KV stayed live.
