# 2026-06-30 - Gemma Q8 Long-Context Prefill Service Gate

Purpose: create and run a stricter prompt-processing / long-context service
gate for the current Gemma 4 26B A4B Q8 record stack, without changing the
short-decode record recipe or accepting any lower-quality target quantization.

This is **service/prefill** work, not a LocalMaxxing short-decode headline.

## New Repro Artifacts

- Fixed deterministic suite:
  `repro/gemma4-26b-a4b-q8-b70/long-context-suite-v1.json`
- Long-context benchmark:
  `scripts/bench-openai-long-context-suite.py`
- Four-GPU paired service gate:
  `repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh`
- Four-GPU paired short-decode guard:
  `repro/gemma4-26b-a4b-q8-b70/run-vdr2-short-decode-guard.sh`

The long-context suite generates deterministic prompts from JSON case specs and
requires exact JSON retrieval fields. Every row records prompt/output hashes,
usage, TTFT, approximate prefill tok/s (`prompt_tokens / TTFT`), decode tok/s
after TTFT, validation status, and `cached_tokens`.

Promotion policy for this service lane:

- each long-context prompt is sent once as a cold request;
- every row must report `cached_tokens=0`;
- exact JSON retrieval validation must pass;
- the target/verifier remains `UD-Q8_K_XL`;
- speculative tokens remain target-verified through the existing MTP path;
- any service/default recipe change must also pass the fixed short realistic
  suite afterward to prove no short-decode regression.

## Smoke

`20260630Tlongsmoke`

Command shape:

```bash
STAMP=20260630Tlongsmoke \
LONG_CONTEXT_CASE_IDS='lc-00512-early' \
LANE_SPECS='0:1024:1024:ub1024-smoke' \
CANARY_REPEATS=1 MAX_TOKENS=96 LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS=512 \
BASE_PORT=18520 \
repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh
```

Result:

- gate passed;
- canary passed;
- actual prompt tokens: `741`;
- `cached_tokens=0`;
- exact JSON output matched all fields;
- approximate prefill: `874.946 tok/s`.

Artifacts:

- `data/gemma4-long-context-service-gate-20260630Tlongsmoke.json`
- `data/gemma4-q8-gpu0-longctx-ub1024-smoke-ctx32768-o96-20260630Tlongsmoke/`

## Paired UB1024 vs UB2048 Service Screen

`20260630TlongctxA`

Command shape:

```bash
STAMP=20260630TlongctxA \
LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS=16384 \
CANARY_REPEATS=4 MAX_TOKENS=96 BASE_PORT=18520 \
repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh
```

Cases selected:

- `lc-00512-early` (`741` actual prompt tokens)
- `lc-02048-middle` (`2806`)
- `lc-04096-late` (`5643`)
- `lc-08192-middle` (`10976`)
- `lc-12288-early` (`16213`)
- `lc-16384-late` (`22730`)

All four lanes passed:

- long-context gate passed;
- canary passed (`16/16` rows per lane);
- exact JSON retrieval passed every case;
- `cached_tokens=0` every case;
- prompts were unique by hash.

Summary:

| Config | Lanes | Median prefill tok/s by lane | Avg median prefill | Long JSON decode median by lane | Avg decode median |
|---|---:|---:|---:|---:|---:|
| UB1024 | 2 | `936.204`, `937.527` | `936.865` | `118.768`, `118.465` | `118.617` |
| UB2048 | 2 | `1007.849`, `1019.918` | `1013.884` | `113.473`, `113.667` | `113.570` |

Readout:

- UB2048 improved median approximate prefill by about
  `+8.22%` versus UB1024 on this fixed long-context suite.
- The long-suite short JSON decode rate was lower for UB2048, so a separate
  short fixed-suite guard is mandatory before treating UB2048 as service-safe.

Artifacts:

- `data/gemma4-long-context-service-gate-20260630TlongctxA.json`
- `data/gemma4-q8-gpu0-longctx-ub1024-a-ctx32768-o96-20260630TlongctxA/`
- `data/gemma4-q8-gpu1-longctx-ub2048-a-ctx32768-o96-20260630TlongctxA/`
- `data/gemma4-q8-gpu2-longctx-ub1024-b-ctx32768-o96-20260630TlongctxA/`
- `data/gemma4-q8-gpu3-longctx-ub2048-b-ctx32768-o96-20260630TlongctxA/`

## Short-Decode Guard

`20260630TshortguardA`

Command shape:

```bash
STAMP=20260630TshortguardA \
CANARY_REPEATS=32 MAX_TOKENS=512 BASE_PORT=18540 \
repro/gemma4-26b-a4b-q8-b70/run-vdr2-short-decode-guard.sh
```

All four lanes passed:

- fixed realistic final gate passed;
- `cached_tokens=0` every prompt;
- canary passed (`128/128` rows per lane);
- target/verifier stayed `UD-Q8_K_XL`.

Summary:

| Config | Lanes | Median 1-100 tok/s by lane | Avg median |
|---|---:|---:|---:|
| UB1024 | 2 | `120.579`, `112.225` | `116.402` |
| UB2048 | 2 | `121.270`, `117.035` | `119.153` |

Readout:

- UB2048 did **not** show a short-decode regression in this paired guard.
- It also did not beat the active `123.67689864739785 tok/s` short record, so
  do not submit it as a LocalMaxxing short-decode record.

Artifacts:

- `data/gemma4-short-decode-guard-20260630TshortguardA.json`
- `data/gemma4-q8-gpu0-shortguard-ub1024-a-ctx32768-o512-20260630TshortguardA/`
- `data/gemma4-q8-gpu1-shortguard-ub2048-a-ctx32768-o512-20260630TshortguardA/`
- `data/gemma4-q8-gpu2-shortguard-ub1024-b-ctx32768-o512-20260630TshortguardA/`
- `data/gemma4-q8-gpu3-shortguard-ub2048-b-ctx32768-o512-20260630TshortguardA/`

## Near-32K Boundary Case

`20260630TlongctxB` tested only `lc-22000-middle`, which became `30400` actual
prompt tokens. It used `MAX_TOKENS=64`, which truncated the exact JSON before
the closing fields. All rows still reported `cached_tokens=0`, and performance
was measurable, but the gate failed quality. Treat this as a harness mistake,
not a model/context failure.

Corrected run: `20260630TlongctxB2`

Command shape:

```bash
STAMP=20260630TlongctxB2 \
LONG_CONTEXT_CASE_IDS='lc-22000-middle' \
LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS=24000 \
CANARY_REPEATS=1 MAX_TOKENS=96 BASE_PORT=18520 \
repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh
```

All four lanes passed:

- actual prompt tokens: `30400`;
- long-context gate passed;
- exact JSON retrieval passed;
- `cached_tokens=0`;
- canary passed (`4/4` rows per lane).

Summary:

| Config | Lanes | Median prefill tok/s by lane | Avg median prefill | Decode median by lane | Avg decode median |
|---|---:|---:|---:|---:|---:|
| UB1024 | 2 | `662.315`, `661.495` | `661.905` | `70.065`, `69.921` | `69.993` |
| UB2048 | 2 | `698.982`, `703.992` | `701.487` | `67.976`, `68.071` | `68.024` |

Readout:

- UB2048 improved approximate prefill by about `+5.98%` at the `30400` actual
  prompt-token boundary.
- Decode after TTFT on the short JSON output is lower for UB2048 at this shape,
  but the fixed short-decode guard above did not show a short-suite regression.

Artifacts:

- failed/truncated:
  `data/gemma4-long-context-service-gate-20260630TlongctxB.json`
- corrected:
  `data/gemma4-long-context-service-gate-20260630TlongctxB2.json`
- corrected lane dirs:
  `data/gemma4-q8-gpu0-longctx-ub1024-a-ctx32768-o96-20260630TlongctxB2/`
  through
  `data/gemma4-q8-gpu3-longctx-ub2048-b-ctx32768-o96-20260630TlongctxB2/`

## Decision

`BATCH_SIZE=2048`, `UBATCH_SIZE=2048` is now the best validated
prompt-processing / long-context **service candidate** for this Gemma Q8 stack:

- fixed long-context gate passes through `22730` actual prompt tokens with
  multi-case coverage;
- corrected boundary gate passes at `30400` actual prompt tokens;
- `cached_tokens=0` on every long-context and short-suite row;
- exact long-context retrieval validation passes;
- fixed short realistic suite passes and shows no decode regression in the
  paired guard.

Keep the promoted short-record recipe at UB1024 unless UB2048 independently
beats the current `123.67689864739785 tok/s` short-decode record. For service
or long-prompt deployments, UB2048 is now a reasonable default candidate, with
UB1024 retained as the strict record reproduction setting.

No LocalMaxxing submission was made: these are service/prefill validation rows,
and the short guard did not break the current record.

## Follow-Up: Heavy-Context UBATCH Refinement

After promoting UB2048 as the general service candidate, two four-GPU
cross-over screens tested only the heavier fixed long-context cases:

- `lc-12288-early` (`16213` actual prompt tokens);
- `lc-16384-late` (`22730` actual prompt tokens);
- `lc-22000-middle` (`30400` actual prompt tokens).

Both screens used unique cold requests, exact JSON retrieval validation,
`cached_tokens=0`, `MAX_TOKENS=96`, and `LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS=24000`.
Every lane passed the long-context gate.

Commands:

```bash
STAMP=20260630Tubatch-refineA \
LONG_CONTEXT_CASE_IDS='lc-12288-early lc-16384-late lc-22000-middle' \
LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS=24000 \
LANE_SPECS='0:1792:1792:ub1792 1:2048:2048:ub2048 2:2304:2304:ub2304 3:2560:2560:ub2560' \
CANARY_REPEATS=2 MAX_TOKENS=96 BASE_PORT=18520 \
repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh

STAMP=20260630Tubatch-refineB \
LONG_CONTEXT_CASE_IDS='lc-12288-early lc-16384-late lc-22000-middle' \
LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS=24000 \
LANE_SPECS='0:2560:2560:ub2560-xover 1:2304:2304:ub2304-xover 2:2048:2048:ub2048-xover 3:1792:1792:ub1792-xover' \
CANARY_REPEATS=2 MAX_TOKENS=96 BASE_PORT=18520 \
repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh
```

Combined A/B readout:

| Config | Avg median prefill tok/s | Avg decode tok/s | 16213-token prefill | 22730-token prefill | 30400-token prefill |
|---|---:|---:|---:|---:|---:|
| UB1792 | `816.264` | `78.377` | `931.816` | `816.264` | `708.444` |
| UB2048 | `815.106` | `78.499` | `938.039` | `815.106` | `710.342` |
| UB2304 | `827.853` | `77.408` | `939.178` | `827.853` | `708.743` |
| UB2560 | `835.782` | `77.519` | `937.321` | `835.782` | `718.968` |

Readout:

- UB2560 is the fastest heavy-context prefill point in this narrow screen:
  about `+2.5%` versus UB2048 on the combined heavy cases and about `+1.2%`
  at `30400` actual prompt tokens.
- UB2304 is close at `22730` actual prompt tokens, but does not win the
  near-32K boundary.
- Larger UBATCH sizes slightly reduce long-suite decode on these short JSON
  outputs, so short-suite guards remain required before any service promotion.

Artifacts:

- `data/gemma4-long-context-service-gate-20260630Tubatch-refineA.json`
- `data/gemma4-long-context-service-gate-20260630Tubatch-refineB.json`
- `data/gemma4-q8-gpu*-longctx-*-20260630Tubatch-refineA*/`
- `data/gemma4-q8-gpu*-longctx-*-20260630Tubatch-refineB*/`

## Follow-Up Short Guards For Larger UBATCH

UB2560 and UB2304 were then tested against the fixed short realistic suite with
the current record stack and `MAX_TOKENS=512`.

Commands:

```bash
STAMP=20260630Tshortguard-ub2560A \
LANE_SPECS='0:1024:1024:ub1024-control 1:2048:2048:ub2048-service 2:2560:2560:ub2560-cand-a 3:2560:2560:ub2560-cand-b' \
CANARY_REPEATS=32 MAX_TOKENS=512 BASE_PORT=18540 \
repro/gemma4-26b-a4b-q8-b70/run-vdr2-short-decode-guard.sh

STAMP=20260630Tshortguard-ub2304A \
LANE_SPECS='0:1024:1024:ub1024-control 1:2048:2048:ub2048-service 2:2304:2304:ub2304-cand-a 3:2304:2304:ub2304-cand-b' \
CANARY_REPEATS=32 MAX_TOKENS=512 BASE_PORT=18540 \
repro/gemma4-26b-a4b-q8-b70/run-vdr2-short-decode-guard.sh
```

Both runs passed the strict cold gate, `cached_tokens=0`, and canaries on every
lane, but neither larger UBATCH is service-safe under the "do not lower short
decode" rule:

| Run | Config | Median 1-100 tok/s after TTFT |
|---|---|---:|
| `20260630Tshortguard-ub2560A` | UB1024 control | `120.084` |
| `20260630Tshortguard-ub2560A` | UB2048 service | `114.841` |
| `20260630Tshortguard-ub2560A` | UB2560 avg | `113.252` |
| `20260630Tshortguard-ub2304A` | UB1024 control | `121.925` |
| `20260630Tshortguard-ub2304A` | UB2048 service | `119.560` |
| `20260630Tshortguard-ub2304A` | UB2304 avg | `116.547` |

Decision:

- Keep UB2048 as the validated general long-context service/default candidate.
- Keep UB1024 for the short-record reproduction lane.
- UB2304 and UB2560 are valid prefill diagnostics only. Do not promote them to
  default service settings unless a future source patch changes the short
  decode tradeoff and they are re-guarded.

Artifacts:

- `data/gemma4-short-decode-guard-20260630Tshortguard-ub2560A.json`
- `data/gemma4-short-decode-guard-20260630Tshortguard-ub2304A.json`
- `data/gemma4-q8-gpu*-shortguard-*-20260630Tshortguard-ub2560A*/`
- `data/gemma4-q8-gpu*-shortguard-*-20260630Tshortguard-ub2304A*/`

## Profile: Near-32K UB2048 Prefill Is Attention-Bound

A diagnostic profile run kept the validated UB2048 service shape and enabled
SYCL node profiling plus server/MTP timing for the `lc-22000-middle` boundary
case. This run is **diagnostic only** because profiling perturbs throughput.

Command:

```bash
STAMP=20260630Tprefill-profile-ub2048 \
GGML_SYCL_NODE_PROFILE=1 \
GGML_SYCL_NODE_PROFILE_DETAIL=1 \
GGML_SYCL_NODE_PROFILE_EVERY=24 \
LLAMA_SERVER_SPEC_PROFILE=1 \
LLAMA_MTP_DRAFT_PROFILE=1 \
LONG_CONTEXT_CASE_IDS='lc-22000-middle' \
LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS=24000 \
LANE_SPECS='0:2048:2048:ub2048-profile' \
CANARY_REPEATS=1 MAX_TOKENS=96 BASE_PORT=18520 \
repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh
```

Result:

- long-context gate passed;
- exact JSON retrieval passed;
- `cached_tokens=0`;
- prompt tokens: `30400`;
- prompt eval: `43193.83 ms / 30400 tokens = 703.80 tok/s`;
- generated eval: `1377.13 ms / 78 tokens = 56.64 tok/s`;
- server profile: `target_prompt_ms=43844.971`, `target_generation_ms=1495.208`;
- MTP profile: `process_ubatch_ms=45291.124` dominates;
- SYCL node profile: `graphs=144`, `unique_nodes=1423`; the top five nodes are
  `FLASH_ATTN_EXT:__fattn__` layers `5`, `17`, `11`, `23`, and `29`, each
  around `4511-4529 ms` total / `55` calls / `~82 ms` average.

Decision:

- The near-32K prompt-processing bottleneck is FlashAttention / KV-cache
  attention work, not verifier LM-head rows or MoE selected-down work.
- Next prefill source work should target the attention/prefill path:
  flash-attention shape handling, KV/cache movement, or prefill graph/layout
  behavior.
- Keep short-decode verifier/MoE ideas separate; they are still relevant to
  the short record, but this profile does not support them as the next
  long-context prefill lever.

Artifacts:

- `data/gemma4-long-context-service-gate-20260630Tprefill-profile-ub2048.json`
- `data/gemma4-q8-gpu0-longctx-ub2048-profile-ctx32768-o96-20260630Tprefill-profile-ub2048/`
- copied profile log:
  `data/gemma4-q8-gpu0-longctx-ub2048-profile-ctx32768-o96-20260630Tprefill-profile-ub2048/server.log`
