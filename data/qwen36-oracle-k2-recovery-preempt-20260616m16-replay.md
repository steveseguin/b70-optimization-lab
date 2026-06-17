# Qwen3.6 Spec Trace Replay

- trace: `/home/steve/llm-optimizations/data/qwen36-oracle-k2-recovery-preempt-20260616m16-spec.jsonl`
- rows: `10`
- malformed rows: `0`
- requests: `2`
- suppressed follow-up mismatches: `0`
- suppressed schedule mismatches: `0`
- suppressed accept mismatches: `0`
- accounting mismatches: `1`

| request | rows | drafts | accepted | rejected | suppressed rows | joined token case | generated mismatches | schedule mismatches | accept mismatches | accounting mismatches |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| `cmpl-qwen36-oracle-k2-recovery-preempt-20260616m16-000000-0-9033432b` | 6 | 12 | 11 | 1 | 0 | `` | 0 | 0 | 0 | 1 |
| `cmpl-qwen36-oracle-k2-recovery-preempt-20260616m16-000001-0-ba58b99a` | 4 | 8 | 8 | 0 | 0 | `` | 0 | 0 | 0 | 0 |

## Accounting Mismatches

- request `cmpl-qwen36-oracle-k2-recovery-preempt-20260616m16-000000-0-9033432b` line `6`: expected computed delta `-1` from rejected `1` plus suppressed `0`, observed `-3`.

## Request Counter Transitions

| request | line | scheduled | accepted | rejected | computed delta | output-token delta | token delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cmpl-qwen36-oracle-k2-recovery-preempt-20260616m16-000000-0-9033432b` | 1 | 3 | 2 | 0 | 0 | 3 | 3 |
| `cmpl-qwen36-oracle-k2-recovery-preempt-20260616m16-000000-0-9033432b` | 2 | 3 | 2 | 0 | 0 | 3 | 3 |
| `cmpl-qwen36-oracle-k2-recovery-preempt-20260616m16-000000-0-9033432b` | 3 | 3 | 2 | 0 | 0 | 3 | 3 |
| `cmpl-qwen36-oracle-k2-recovery-preempt-20260616m16-000000-0-9033432b` | 4 | 3 | 2 | 0 | 0 | 3 | 3 |
| `cmpl-qwen36-oracle-k2-recovery-preempt-20260616m16-000000-0-9033432b` | 5 | 3 | 2 | 0 | 0 | 3 | 3 |
| `cmpl-qwen36-oracle-k2-recovery-preempt-20260616m16-000000-0-9033432b` | 6 | 3 | 1 | 1 | -3 | 0 | 0 |
| `cmpl-qwen36-oracle-k2-recovery-preempt-20260616m16-000001-0-ba58b99a` | 7 | 3 | 2 | 0 | 0 | 3 | 3 |
| `cmpl-qwen36-oracle-k2-recovery-preempt-20260616m16-000001-0-ba58b99a` | 8 | 3 | 2 | 0 | 0 | 3 | 3 |
| `cmpl-qwen36-oracle-k2-recovery-preempt-20260616m16-000001-0-ba58b99a` | 9 | 3 | 2 | 0 | 0 | 3 | 3 |
| `cmpl-qwen36-oracle-k2-recovery-preempt-20260616m16-000001-0-ba58b99a` | 10 | 3 | 2 | 0 | 0 | 3 | 3 |

Post-output `computed_minus_tokens` is included in the JSON rows.
Values below zero usually mean the next pass may recompute an already
emitted token; values above zero after suppressing a bonus can mean stale
unemitted KV stayed live.
