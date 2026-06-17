# Qwen3.6 Spec Trace Replay

- trace: `data/qwen36-oracle-ngram1-c1capture-20260615oraclec1cap2.jsonl`
- rows: `34`
- malformed rows: `0`
- requests: `1`
- suppressed follow-up mismatches: `0`
- suppressed schedule mismatches: `0`
- suppressed accept mismatches: `0`
- accounting mismatches: `0`

| request | rows | drafts | accepted | rejected | suppressed rows | joined token case | generated mismatches | schedule mismatches | accept mismatches | accounting mismatches |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| `cmpl-ngram-c1cap-20260615oraclec1cap2-000000-0-986d480b` | 34 | 34 | 31 | 3 | 0 | `natural_latency_plan (scheduler_prefix)` | 0 | 0 | 0 | 0 |

## Request Counter Transitions

| request | line | scheduled | accepted | rejected | computed delta | output-token delta | token delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cmpl-ngram-c1cap-20260615oraclec1cap2-000000-0-986d480b` | 1 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ngram-c1cap-20260615oraclec1cap2-000000-0-986d480b` | 2 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ngram-c1cap-20260615oraclec1cap2-000000-0-986d480b` | 3 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ngram-c1cap-20260615oraclec1cap2-000000-0-986d480b` | 4 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ngram-c1cap-20260615oraclec1cap2-000000-0-986d480b` | 5 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ngram-c1cap-20260615oraclec1cap2-000000-0-986d480b` | 6 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ngram-c1cap-20260615oraclec1cap2-000000-0-986d480b` | 7 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ngram-c1cap-20260615oraclec1cap2-000000-0-986d480b` | 8 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ngram-c1cap-20260615oraclec1cap2-000000-0-986d480b` | 9 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ngram-c1cap-20260615oraclec1cap2-000000-0-986d480b` | 10 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ngram-c1cap-20260615oraclec1cap2-000000-0-986d480b` | 11 | 2 | 0 | 1 | -1 | 1 | 1 |
| `cmpl-ngram-c1cap-20260615oraclec1cap2-000000-0-986d480b` | 12 | 2 | 0 | 1 | -1 | 1 | 1 |
| `cmpl-ngram-c1cap-20260615oraclec1cap2-000000-0-986d480b` | 13 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ngram-c1cap-20260615oraclec1cap2-000000-0-986d480b` | 14 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ngram-c1cap-20260615oraclec1cap2-000000-0-986d480b` | 15 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ngram-c1cap-20260615oraclec1cap2-000000-0-986d480b` | 16 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ngram-c1cap-20260615oraclec1cap2-000000-0-986d480b` | 17 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ngram-c1cap-20260615oraclec1cap2-000000-0-986d480b` | 18 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ngram-c1cap-20260615oraclec1cap2-000000-0-986d480b` | 19 | 2 | 1 | 0 | 0 | 2 | 2 |
| `cmpl-ngram-c1cap-20260615oraclec1cap2-000000-0-986d480b` | 20 | 2 | 1 | 0 | 0 | 2 | 2 |

Post-output `computed_minus_tokens` is included in the JSON rows.
Values below zero usually mean the next pass may recompute an already
emitted token; values above zero after suppressing a bonus can mean stale
unemitted KV stayed live.
