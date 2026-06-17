# Qwen3.6 Spec Trace Replay

- trace: `/home/steve/llm-optimizations/data/qwen36-oracle-k1-draftsonly-noskip-20260616m4-spec.jsonl`
- rows: `32`
- malformed rows: `0`
- requests: `2`
- suppressed follow-up mismatches: `30`
- suppressed schedule mismatches: `30`
- suppressed accept mismatches: `30`
- accounting mismatches: `0`

| request | rows | drafts | accepted | rejected | suppressed rows | joined token case | generated mismatches | schedule mismatches | accept mismatches | accounting mismatches |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000000-0-8e16b73d` | 16 | 16 | 16 | 0 | 16 | `natural_latency_plan (scheduler_prefix)` | 15 | 15 | 15 | 0 |
| `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000001-0-9a91d3f7` | 16 | 16 | 16 | 0 | 16 | `repetitive_kernel_notes (scheduler_prefix)` | 15 | 15 | 15 | 0 |

## Suppressed Follow-Up Mismatches

- request `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000000-0-8e16b73d` line `1` -> `2`:
  suppressed `27044` ` dense`, next scheduled `47193` ` numbered`, next verifier token was `47193` ` numbered`, next emitted `47193` ` numbered`.
- request `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000000-0-8e16b73d` line `2` -> `3`:
  suppressed `14246` ` engineering`, next scheduled `8129` ` notes`, next verifier token was `8129` ` notes`, next emitted `8129` ` notes`.
- request `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000000-0-8e16b73d` line `3` -> `4`:
  suppressed `13` `.`, next scheduled `24985` ` Focus`, next verifier token was `24985` ` Focus`, next emitted `24985` ` Focus`.
- request `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000000-0-8e16b73d` line `4` -> `5`:
  suppressed `383` ` on`, next scheduled `3074` ` single`, next verifier token was `3074` ` single`, next emitted `3074` ` single`.
- request `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000000-0-8e16b73d` line `5` -> `6`:
  suppressed `43318` `-request`, next scheduled `16401` ` decode`, next verifier token was `16401` ` decode`, next emitted `16401` ` decode`.
- request `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000000-0-8e16b73d` line `6` -> `7`:
  suppressed `4478` ` speed`, next scheduled `11` `,`, next verifier token was `11` `,`, next emitted `11` `,`.
- request `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000000-0-8e16b73d` line `7` -> `8`:
  suppressed `29541` ` reliability`, next scheduled `33389` ` gates`, next verifier token was `33389` ` gates`, next emitted `33389` ` gates`.
- request `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000000-0-8e16b73d` line `8` -> `9`:
  suppressed `11` `,`, next scheduled `11436` ` hardware`, next verifier token was `11436` ` hardware`, next emitted `11436` ` hardware`.
- request `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000000-0-8e16b73d` line `9` -> `10`:
  suppressed `29796` ` acceleration`, next scheduled `11` `,`, next verifier token was `11` `,`, next emitted `11` `,`.
- request `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000000-0-8e16b73d` line `10` -> `11`:
  suppressed `321` ` and`, next scheduled `874` ` no`, next verifier token was `874` ` no`, next emitted `874` ` no`.
- request `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000000-0-8e16b73d` line `11` -> `12`:
  suppressed `4131` ` quality`, next scheduled `4557` ` loss`, next verifier token was `4557` ` loss`, next emitted `4557` ` loss`.
- request `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000000-0-8e16b73d` line `12` -> `13`:
  suppressed `13` `.`, next scheduled `271` `

`, next verifier token was `271` `

`, next emitted `271` `

`.
- request `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000000-0-8e16b73d` line `13` -> `14`:
  suppressed `248068` `<think>`, next scheduled `198` `
`, next verifier token was `198` `
`, next emitted `198` `
`.
- request `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000000-0-8e16b73d` line `14` -> `15`:
  suppressed `8160` `Here`, next scheduled `8340` ` Process`, next verifier token was `8340` ` Process`, next emitted `8340` ` Process`.
- request `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000000-0-8e16b73d` line `15` -> `16`:
  suppressed `25` `:`, next scheduled `271` `

`, next verifier token was `271` `

`, next emitted `271` `

`.
- request `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000001-0-9a91d3f7` line `17` -> `18`:
  suppressed `13` `.`, next scheduled `78503` ` Preserve`, next verifier token was `78503` ` Preserve`, next emitted `78503` ` Preserve`.
- request `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000001-0-9a91d3f7` line `18` -> `19`:
  suppressed `4581` ` exact`, next scheduled `2468` ` output`, next verifier token was `2468` ` output`, next emitted `2468` ` output`.
- request `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000001-0-9a91d3f7` line `19` -> `20`:
  suppressed `1345` ` while`, next scheduled `28043` ` measuring`, next verifier token was `28043` ` measuring`, next emitted `28043` ` measuring`.
- request `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000001-0-9a91d3f7` line `20` -> `21`:
  suppressed `7072` ` multi`, next scheduled `3817` ` token`, next verifier token was `3817` ` token`, next emitted `3817` ` token`.
- request `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000001-0-9a91d3f7` line `21` -> `22`:
  suppressed `22188` ` verification`, next scheduled `13` `.`, next verifier token was `13` `.`, next emitted `13` `.`.
- request `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000001-0-9a91d3f7` line `22` -> `23`:
  suppressed `15153` ` Intel`, next scheduled `1543` ` X`, next verifier token was `1543` ` X`, next emitted `1543` ` X`.
- request `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000001-0-9a91d3f7` line `23` -> `24`:
  suppressed `6126` `PU`, next scheduled `16401` ` decode`, next verifier token was `16401` ` decode`, next emitted `16401` ` decode`.
- request `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000001-0-9a91d3f7` line `24` -> `25`:
  suppressed `85683` ` verifier`, next scheduled `15162` ` bucket`, next verifier token was `15162` ` bucket`, next emitted `15162` ` bucket`.
- request `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000001-0-9a91d3f7` line `25` -> `26`:
  suppressed `5832` ` route`, next scheduled `271` `

`, next verifier token was `271` `

`, next emitted `271` `

`.
- request `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000001-0-9a91d3f7` line `26` -> `27`:
  suppressed `248068` `<think>`, next scheduled `271` `

`, next verifier token was `271` `

`, next emitted `271` `

`.
- request `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000001-0-9a91d3f7` line `27` -> `28`:
  suppressed `248069` `</think>`, next scheduled `271` `

`, next verifier token was `271` `

`, next emitted `271` `

`.
- request `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000001-0-9a91d3f7` line `28` -> `29`:
  suppressed `47452` `Intel`, next scheduled `1543` ` X`, next verifier token was `1543` ` X`, next emitted `1543` ` X`.
- request `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000001-0-9a91d3f7` line `29` -> `30`:
  suppressed `6126` `PU`, next scheduled `16401` ` decode`, next verifier token was `16401` ` decode`, next emitted `16401` ` decode`.
- request `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000001-0-9a91d3f7` line `30` -> `31`:
  suppressed `85683` ` verifier`, next scheduled `15162` ` bucket`, next verifier token was `15162` ` bucket`, next emitted `15162` ` bucket`.
- request `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000001-0-9a91d3f7` line `31` -> `32`:
  suppressed `5832` ` route`, next scheduled `4618` ` graph`, next verifier token was `4618` ` graph`, next emitted `4618` ` graph`.

## Request Counter Transitions

| request | line | scheduled | accepted | rejected | computed delta | output-token delta | token delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000000-0-8e16b73d` | 1 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000000-0-8e16b73d` | 2 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000000-0-8e16b73d` | 3 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000000-0-8e16b73d` | 4 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000000-0-8e16b73d` | 5 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000000-0-8e16b73d` | 6 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000000-0-8e16b73d` | 7 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000000-0-8e16b73d` | 8 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000000-0-8e16b73d` | 9 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000000-0-8e16b73d` | 10 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000000-0-8e16b73d` | 11 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000000-0-8e16b73d` | 12 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000000-0-8e16b73d` | 13 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000000-0-8e16b73d` | 14 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000000-0-8e16b73d` | 15 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000000-0-8e16b73d` | 16 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000001-0-9a91d3f7` | 17 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000001-0-9a91d3f7` | 18 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000001-0-9a91d3f7` | 19 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-qwen36-oracle-k1-draftsonly-noskip-20260616m4-000001-0-9a91d3f7` | 20 | 2 | 1 | 0 | -1 | 1 | 1 |

Post-output `computed_minus_tokens` is included in the JSON rows.
Values below zero usually mean the next pass may recompute an already
emitted token; values above zero after suppressing a bonus can mean stale
unemitted KV stayed live.
