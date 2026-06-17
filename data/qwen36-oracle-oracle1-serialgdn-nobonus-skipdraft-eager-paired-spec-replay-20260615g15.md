# Qwen3.6 Spec Trace Replay

- trace: `/home/steve/llm-optimizations/data/qwen36-oracle1-serialgdn-nobonus-skipdraft-eager-paired-20260615g15-spec-trace.jsonl`
- rows: `28`
- malformed rows: `0`
- requests: `2`
- suppressed follow-up mismatches: `25`
- suppressed schedule mismatches: `25`
- suppressed accept mismatches: `25`
- accounting mismatches: `0`

| request | rows | drafts | accepted | rejected | suppressed rows | joined token case | generated mismatches | schedule mismatches | accept mismatches | accounting mismatches |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| `cmpl-a88b2797c1a1a5c4-0-be8d2e0d` | 16 | 16 | 16 | 0 | 16 | `repetitive_kernel_notes (scheduler_prefix)` | 15 | 15 | 15 | 0 |
| `cmpl-a10e1749ff57ba54-0-97d8299c` | 12 | 12 | 10 | 2 | 10 | `natural_latency_plan (scheduler_prefix)` | 10 | 10 | 10 | 0 |

## Suppressed Follow-Up Mismatches

- request `cmpl-a88b2797c1a1a5c4-0-be8d2e0d` line `13` -> `14`:
  suppressed `220` ` `, next scheduled `78503` ` Preserve`, next verifier token was `78503` ` Preserve`, next emitted `78503` ` Preserve`.
- request `cmpl-a88b2797c1a1a5c4-0-be8d2e0d` line `14` -> `15`:
  suppressed `220` ` `, next scheduled `2468` ` output`, next verifier token was `2468` ` output`, next emitted `2468` ` output`.
- request `cmpl-a88b2797c1a1a5c4-0-be8d2e0d` line `15` -> `16`:
  suppressed `220` ` `, next scheduled `28043` ` measuring`, next verifier token was `28043` ` measuring`, next emitted `28043` ` measuring`.
- request `cmpl-a88b2797c1a1a5c4-0-be8d2e0d` line `16` -> `17`:
  suppressed `220` ` `, next scheduled `3817` ` token`, next verifier token was `3817` ` token`, next emitted `3817` ` token`.
- request `cmpl-a88b2797c1a1a5c4-0-be8d2e0d` line `17` -> `18`:
  suppressed `220` ` `, next scheduled `13` `.`, next verifier token was `13` `.`, next emitted `13` `.`.
- request `cmpl-a88b2797c1a1a5c4-0-be8d2e0d` line `18` -> `19`:
  suppressed `173439` ` hels`, next scheduled `1543` ` X`, next verifier token was `1543` ` X`, next emitted `1543` ` X`.
- request `cmpl-a88b2797c1a1a5c4-0-be8d2e0d` line `19` -> `20`:
  suppressed `220` ` `, next scheduled `16401` ` decode`, next verifier token was `16401` ` decode`, next emitted `16401` ` decode`.
- request `cmpl-a88b2797c1a1a5c4-0-be8d2e0d` line `20` -> `21`:
  suppressed `220` ` `, next scheduled `15162` ` bucket`, next verifier token was `15162` ` bucket`, next emitted `15162` ` bucket`.
- request `cmpl-a88b2797c1a1a5c4-0-be8d2e0d` line `21` -> `22`:
  suppressed `220` ` `, next scheduled `4618` ` graph`, next verifier token was `4618` ` graph`, next emitted `4618` ` graph`.
- request `cmpl-a88b2797c1a1a5c4-0-be8d2e0d` line `22` -> `23`:
  suppressed `184475` ` existi`, next scheduled `17856` ` timing`, next verifier token was `17856` ` timing`, next emitted `17856` ` timing`.
- request `cmpl-a88b2797c1a1a5c4-0-be8d2e0d` line `23` -> `24`:
  suppressed `220` ` `, next scheduled `78503` ` Preserve`, next verifier token was `78503` ` Preserve`, next emitted `78503` ` Preserve`.
- request `cmpl-a88b2797c1a1a5c4-0-be8d2e0d` line `24` -> `25`:
  suppressed `220` ` `, next scheduled `2468` ` output`, next verifier token was `2468` ` output`, next emitted `2468` ` output`.
- request `cmpl-a88b2797c1a1a5c4-0-be8d2e0d` line `25` -> `26`:
  suppressed `220` ` `, next scheduled `28043` ` measuring`, next verifier token was `28043` ` measuring`, next emitted `28043` ` measuring`.
- request `cmpl-a88b2797c1a1a5c4-0-be8d2e0d` line `26` -> `27`:
  suppressed `220` ` `, next scheduled `3817` ` token`, next verifier token was `3817` ` token`, next emitted `3817` ` token`.
- request `cmpl-a88b2797c1a1a5c4-0-be8d2e0d` line `27` -> `28`:
  suppressed `220` ` `, next scheduled `13` `.`, next verifier token was `13` `.`, next emitted `13` `.`.
- request `cmpl-a10e1749ff57ba54-0-97d8299c` line `1` -> `2`:
  suppressed `220` ` `, next scheduled `14246` ` engineering`, next verifier token was `14246` ` engineering`, next emitted `14246` ` engineering`.
- request `cmpl-a10e1749ff57ba54-0-97d8299c` line `2` -> `3`:
  suppressed `220` ` `, next scheduled `13` `.`, next verifier token was `13` `.`, next emitted `13` `.`.
- request `cmpl-a10e1749ff57ba54-0-97d8299c` line `3` -> `4`:
  suppressed `220` ` `, next scheduled `383` ` on`, next verifier token was `383` ` on`, next emitted `383` ` on`.
- request `cmpl-a10e1749ff57ba54-0-97d8299c` line `4` -> `5`:
  suppressed `220` ` `, next scheduled `43318` `-request`, next verifier token was `43318` `-request`, next emitted `43318` `-request`.
- request `cmpl-a10e1749ff57ba54-0-97d8299c` line `5` -> `6`:
  suppressed `220` ` `, next scheduled `4478` ` speed`, next verifier token was `4478` ` speed`, next emitted `4478` ` speed`.
- request `cmpl-a10e1749ff57ba54-0-97d8299c` line `6` -> `7`:
  suppressed `14` `/`, next scheduled `29541` ` reliability`, next verifier token was `29541` ` reliability`, next emitted `29541` ` reliability`.
- request `cmpl-a10e1749ff57ba54-0-97d8299c` line `7` -> `8`:
  suppressed `220` ` `, next scheduled `11` `,`, next verifier token was `11` `,`, next emitted `11` `,`.
- request `cmpl-a10e1749ff57ba54-0-97d8299c` line `8` -> `9`:
  suppressed `220` ` `, next scheduled `4581` ` exact`, next verifier token was `874` ` no`, next emitted `874` ` no`.
- request `cmpl-a10e1749ff57ba54-0-97d8299c` line `10` -> `11`:
  suppressed `220` ` `, next scheduled `13` `.`, next verifier token was `13` `.`, next emitted `13` `.`.
- request `cmpl-a10e1749ff57ba54-0-97d8299c` line `11` -> `12`:
  suppressed `38118` `ان`, next scheduled `760` `The`, next verifier token was `248068` `<think>`, next emitted `248068` `<think>`.

## Request Counter Transitions

| request | line | scheduled | accepted | rejected | computed delta | output-token delta | token delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cmpl-a88b2797c1a1a5c4-0-be8d2e0d` | 13 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-a88b2797c1a1a5c4-0-be8d2e0d` | 14 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-a88b2797c1a1a5c4-0-be8d2e0d` | 15 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-a88b2797c1a1a5c4-0-be8d2e0d` | 16 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-a88b2797c1a1a5c4-0-be8d2e0d` | 17 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-a88b2797c1a1a5c4-0-be8d2e0d` | 18 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-a88b2797c1a1a5c4-0-be8d2e0d` | 19 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-a88b2797c1a1a5c4-0-be8d2e0d` | 20 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-a88b2797c1a1a5c4-0-be8d2e0d` | 21 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-a88b2797c1a1a5c4-0-be8d2e0d` | 22 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-a88b2797c1a1a5c4-0-be8d2e0d` | 23 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-a88b2797c1a1a5c4-0-be8d2e0d` | 24 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-a88b2797c1a1a5c4-0-be8d2e0d` | 25 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-a88b2797c1a1a5c4-0-be8d2e0d` | 26 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-a88b2797c1a1a5c4-0-be8d2e0d` | 27 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-a88b2797c1a1a5c4-0-be8d2e0d` | 28 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-a10e1749ff57ba54-0-97d8299c` | 1 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-a10e1749ff57ba54-0-97d8299c` | 2 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-a10e1749ff57ba54-0-97d8299c` | 3 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-a10e1749ff57ba54-0-97d8299c` | 4 | 2 | 1 | 0 | -1 | 1 | 1 |

Post-output `computed_minus_tokens` is included in the JSON rows.
Values below zero usually mean the next pass may recompute an already
emitted token; values above zero after suppressing a bonus can mean stale
unemitted KV stayed live.
