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
