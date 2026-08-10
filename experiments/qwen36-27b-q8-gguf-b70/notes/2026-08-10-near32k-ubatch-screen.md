# Near-32K `-ub 1024` screen and band decision

Date: 2026-08-10

## Result

A two-wave, same-card crossover on all four B70s found a large prompt-
processing win from changing only llama.cpp microbatch size from `-ub 128` to
`-ub 1024` at c1/F16-KV/32K. Across four observations per arm, mean approximate
prompt processing increased from `155.28150180463635` to
`622.1036995029367 tok/s` (`4.0062962572684375x`), while mean TTFT fell from
`205.08825869824796` to `51.196506101499835 s` (`-75.03684197893226%`). Mean
request elapsed time fell from `212.44424930575042` to
`58.5563289242491 s` (`-72.43684914248978%`).

Natural 94-token decode stayed effectively flat:
`12.778702001069052 -> 12.772049671893084 tok/s`
(`0.9994794205878336x`, `-0.05205794121664331%`). Every run used 31,846
prompt tokens, returned 94 completion tokens with `cached_tokens=0`, fully
offloaded `65/65` layers, and produced the same exact response SHA-256:
`603b44deaf794c77011f3263a5f39e793e9e29dc0cb98efdb8c05ecb64f83972`.

This is strong causal screening evidence because every card saw both settings
and wave order was balanced across cards. It is nevertheless sealed as
`legacy-validation`, `performance_promotable=false`; the one-case natural-stop
screen is not an official full-512 performance packet or a LocalMaxxing result.

## Sealed lanes

| Wave | GPU | `-ub` | PP tok/s | TTFT s | Decode tok/s | Elapsed s | Run directory | Artifact-manifest SHA-256 |
|---:|---:|---:|---:|---:|---:|---:|---|---|
| 1 | 0 | 128 | 155.815911 | 204.382209 | 12.779172 | 211.737928 | `/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/near32k-ubatch-wave1-gpu0-ub128-20260810T040942.697666277Z` | `18f5dba429eaae5625f32d7978e6b00b617e69f96b979f25ef431429745ffdd2` |
| 1 | 1 | 1024 | 611.917004 | 52.043006 | 12.767936 | 59.405198 | `/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/near32k-ubatch-wave1-gpu1-ub1024-20260810T040947.699718384Z` | `6c2c8b6308fd7f9a500d0f2d8d3a183ac7982c59a6b48c67fe4760a842a31204` |
| 1 | 2 | 128 | 155.754680 | 204.462556 | 12.785915 | 211.814395 | `/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/near32k-ubatch-wave1-gpu2-ub128-20260810T040952.701518542Z` | `77a34a57ce6f5bc4735158e7038718ca39d38e6b9ecdb80f0e34177862b0d7ef` |
| 1 | 3 | 1024 | 624.470376 | 50.996815 | 12.774410 | 58.355276 | `/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/near32k-ubatch-wave1-gpu3-ub1024-20260810T040957.704322881Z` | `a050a9d901dee495ae922279f6faa44a06e851bdf234a75cf6b4055e2af59335` |
| 2 | 0 | 1024 | 622.077090 | 51.193012 | 12.764761 | 58.557035 | `/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/near32k-ubatch-wave2-gpu0-ub1024-20260810T041532.365802939Z` | `4d550eb19ae21ff21a3f3748c65fd96395a1749554c09e9ac60c99059e32f8a8` |
| 2 | 1 | 128 | 154.437936 | 206.205812 | 12.774184 | 213.564404 | `/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/near32k-ubatch-wave2-gpu1-ub128-20260810T041537.366953745Z` | `77ebd91996443a1523a466e55d7519b326efed2cbf2468d30817dd3f525ffc27` |
| 2 | 2 | 1024 | 629.950328 | 50.553192 | 12.781092 | 57.907806 | `/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/near32k-ubatch-wave2-gpu2-ub1024-20260810T041542.369503294Z` | `5b67c82a89124fbb5c50413086ed394fe4222a650dec4ebdb12d6bc2c41339e5` |
| 2 | 3 | 128 | 155.117480 | 205.302458 | 12.775537 | 212.660270 | `/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/near32k-ubatch-wave2-gpu3-ub128-20260810T041547.371696000Z` | `50ce4d458551e4e66273570a523e0ddea5b9362c3d220517c1ccb53592590ea7` |

All eight artifact manifests verify. Every detached completion marker reports
`PASS`, `evidence_valid=true`, `evidence_class=legacy-validation`, and
`performance_promotable=false`. Each cleanup record reports no forced kill or
survivor, a closed port, unchanged model/runtime identity, and final 43 MiB
device use. Full-offload and retrieval checks pass in every lane.

## Official isolated near-32K result

The immediate promotion gate subsequently passed on isolated GPU 0:

`/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/goal2-prefill-ub1024-isolated-gpu0-near32k-prefill-ub1024-ub1024-20260810T042909.708244180Z`

- 79/79-entry artifact-manifest SHA-256:
  `d4ccb9d04cfb08d1e928a8ca2a4e76d9b602718680c6a039ec0f776ba2f4656c`;
- exact-result SHA-256:
  `1166c210924483538a15ae873c1abeabf4a7a6345b84b3f69a19be0c8141baa3`;
- detached completion-marker SHA-256:
  `4e61254313eba44bf282835cf461978588c02ca952437e41f954dcf352239001`;
- status: `PASS`, `evidence_valid=true`, `official-isolated`,
  `performance_promotable=true`;
- oracle: `PASS_ORACLE_EXACT`; both 512-token rows are token/content/rendered-
  prompt exact, and the intrinsic, exact-result, and post-512 canary gates pass;
- median prompt processing: `629.2050294524228 tok/s`;
- median TTFT: `50.65979567649629 s`;
- primary conventional tokens 1--100 decode:
  `12.647508019541377 tok/s`;
- conventional tokens 1--512 decode: `12.643250550624003 tok/s`;
- legacy full-512-after-TTFT compatibility rate:
  `12.667340518467988 tok/s`.

Both near-32K prompts generated exactly 512 tokens with `cache_n=0`; full
`65/65` offload passed. Cleanup was graceful, GPU 0 returned `43 -> 43 MiB`,
the port closed, and device/server fault scans were empty.

This promotes `-ub 1024` only for the isolated near-32K prompt-processing and
TTFT row. It clears both the baseline and stretch near-32K PP/TTFT thresholds,
but the conventional full-window decode target remains unmet:
`12.643250550624003 < 18 tok/s`.

## Official isolated short result

The short full-512 guard subsequently passed on isolated GPU 0:

`/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/goal2-prefill-ub1024-isolated-gpu0-short-prefill-ub1024-ub1024-20260810T043918.549062817Z`

- 79/79-entry artifact-manifest SHA-256:
  `a61c0d39f718fb031e12bdaba6a920938204bf1193444a18b0979892aa48f132`;
- exact-result SHA-256:
  `44447d85de5d522418a554d9ef05b52e981f496e9954459496b23fcc6f7f6754`;
- detached completion-marker SHA-256:
  `54ea2f5e9c45ca4dabf6759cc2c18004eab87cfe4836445b89b3e59d758535c6`;
- status: `PASS`, `evidence_valid=true`, `official-isolated`,
  `performance_promotable=true`, and `PASS_ORACLE_EXACT`;
- median PP `605.8452528247487 tok/s`, TTFT `7.190860373499163 s`,
  conventional tokens 1--100 decode `15.08129002631069 tok/s`, and
  conventional tokens 1--512 decode `15.08352908516806 tok/s`.

Both rows are token/content/rendered-prompt exact, and the intrinsic,
exact-result, post-512 canary, cache-zero, full-offload, and cleanup gates pass.
This clears the baseline and stretch short PP/TTFT thresholds, but not the
full-window decode target: `15.08352908516806 < 20 tok/s`. Bank only the
official short PP/TTFT row.

## Middle rejection and matched control

The isolated GPU-0 middle `-ub 1024` candidate failed the exact-output gate:

`/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/goal2-prefill-ub1024-isolated-gpu0-middle-prefill-ub1024-ub1024-20260810T044337.630129063Z`

- 78/78-entry failure-manifest SHA-256:
  `85bbf378748ac87cbfa9c05461dff45bc694c24c23c990852a72946ea5e5ec47`;
- exact-result SHA-256:
  `d3b3899c55ed28b3441f5c7c0fe995342797e1158286066d67dba3da901b8db2`;
- no completion marker was emitted because the packet stopped at
  `FAIL_ORACLE_EXACT`;
- row 1 is exact; row 2 has a 92-token common prefix and first differs at
  generated token 93, candidate `90` versus oracle `71093`;
- the requested JSON fields remain semantically correct, and stream/replay
  exactness, the intrinsic gate, and the post-512 canary pass;
- diagnostic-only medians are PP `656.5809725228953 tok/s`, TTFT
  `26.26653541050473 s`, and conventional D512
  `13.826049180316907 tok/s`.

The failure manifest verifies, all rows are cache-zero and fully offloaded, and
cleanup is clean. Performance is non-promotable under the exact-output policy.

A matched same-card control then passed at `-ub 128`:

`/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/goal2-middle-gpu0-localcontrol-ub128-goal1-baseline-ub128-ub128-20260810T045046.449271344Z`

- 77/77-entry artifact-manifest SHA-256:
  `ff1c24ccb3ec7c1eb1dafccd0218261c156b16687c5a7bfcd60c5d23667396e9`;
- exact-result SHA-256:
  `f493fa009ca29efa7984b62ea3ab1dd7007dab59d596e4071728d815f288c48f`;
- detached completion-marker SHA-256:
  `961a9629b7903565233764fa3aac32e1cf8dc648c6b7343e355c2000cb0d4a80`;
- status: `PASS`, `evidence_valid=true`, `official-isolated`, with exact
  intrinsic/result/post-canary, cache-zero, full-offload, and cleanup gates.

The control packet's own oracle field is correctly
`BASELINE_CAPTURE_READY`. A direct row comparison against the old GPU-1 middle
oracle at
`/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/goal1-four-gpu-functional-20260809T161652.861663620Z/gpu1-middle/exact-tokens.json`
(SHA-256 `38ea99cd3502243b254f459687a081aa7919837db38977aee0d285d878de189c`)
shows both rows exactly match in token IDs, content, and rendered prompt.

The same GPU and current epoch therefore reproduce the old oracle at `-ub 128`
but diverge at `-ub 1024`; within this controlled comparison, the middle
divergence is attributable to the ubatch treatment rather than card or epoch.
Do not make `-ub 1024` a broad default. Bank the scoped official short and
near-32K PP/TTFT wins, reject the middle band under exact policy, and move to
the decode VDR2 screen rather than another ubatch gate.
