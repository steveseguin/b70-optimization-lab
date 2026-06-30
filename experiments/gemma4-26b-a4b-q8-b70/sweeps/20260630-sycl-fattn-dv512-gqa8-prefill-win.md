# 2026-06-30 - SYCL FlashAttention DV512/GQA8 Prefill Win

Purpose: speed up Gemma 4 26B A4B Q8 long-context prompt processing without
changing target quality, quantization, cache policy, or the promoted short
decode recipe.

This is a **service/prefill** win, not a LocalMaxxing short-decode headline.

## Patch

Source worktree:

- `/home/steve/src/llama.cpp-gemma-record-repro-c926`
- llama.cpp base commit: `c926ad098`

Patch artifact:

- `patches/gemma4-26b-a4b-q8-b70/20260630-sycl-fattn-dv512-gqa8-ncols2.patch`
- diffstat:
  `patches/gemma4-26b-a4b-q8-b70/20260630-sycl-fattn-dv512-gqa8-ncols2.diffstat`

Change:

- adds default-off env knob `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8`;
- only affects the SYCL FlashAttention tile path for `DV=512`, GQA-enabled
  masks, and `gqa_ratio % 8 == 0`;
- default behavior is unchanged when the env var is unset.

Rationale:

- near-32K profiling showed `FLASH_ATTN_EXT:__fattn__` dominates prompt
  processing;
- Gemma full-attention layers use `DKQ=512`, `DV=512`, Q heads `16`, KV heads
  `2`, so `gqa_ratio=8`;
- the default selector uses `ncols2=4` for this shape; forcing `ncols2=8`
  reduces the number of GQA tiles and improves B70 long-context throughput.

Build:

```bash
cd /home/steve/src/llama.cpp-gemma-record-repro-c926
source /opt/intel/oneapi/setvars.sh
cmake --build build-sycl-b70-aot-bmg-g31-q8reorder-vdr2 --target llama-server -j 8
```

## Paired Near-32K Crossover

Case:

- `lc-22000-middle`;
- actual prompt tokens: `30400`;
- `MAX_TOKENS=96`;
- exact JSON validation;
- `cached_tokens=0`;
- one cold request per lane;
- target/verifier stayed `UD-Q8_K_XL`;
- output hash was identical for control and candidate:
  `a2c9ffd867b906c1f59e57e7b647e91bae0909b04f7f8de3883c6fae77dfdf72`.

Commands:

```bash
# A: control on GPU0, candidate on GPU1.
LONG_CONTEXT_CASE_IDS='lc-22000-middle' \
LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS=24000 \
CANARY_REPEATS=1 MAX_TOKENS=96 BASE_PORT=18520 \
STAMP=20260630Tfattn-gqa8-controlA \
LANE_SPECS='0:2048:2048:ub2048-control' \
repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh

GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8 \
LONG_CONTEXT_CASE_IDS='lc-22000-middle' \
LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS=24000 \
CANARY_REPEATS=1 MAX_TOKENS=96 BASE_PORT=18520 \
STAMP=20260630Tfattn-gqa8-candidateA \
LANE_SPECS='1:2048:2048:ub2048-gqa8' \
repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh

# B: crossover, candidate on GPU0, control on GPU1.
GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8 \
LONG_CONTEXT_CASE_IDS='lc-22000-middle' \
LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS=24000 \
CANARY_REPEATS=1 MAX_TOKENS=96 BASE_PORT=18520 \
STAMP=20260630Tfattn-gqa8-candidateB \
LANE_SPECS='0:2048:2048:ub2048-gqa8-xover' \
repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh

LONG_CONTEXT_CASE_IDS='lc-22000-middle' \
LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS=24000 \
CANARY_REPEATS=1 MAX_TOKENS=96 BASE_PORT=18520 \
STAMP=20260630Tfattn-gqa8-controlB \
LANE_SPECS='1:2048:2048:ub2048-control-xover' \
repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh
```

Results:

| Lane | GPU | Prefill tok/s | Decode tok/s | TTFT s | Gate |
|---|---:|---:|---:|---:|---|
| controlA | 0 | `706.901` | `68.245` | `43.005` | pass |
| candidateA | 1 | `939.976` | `113.140` | `32.341` | pass |
| candidateB | 0 | `955.203` | `113.471` | `31.826` | pass |
| controlB | 1 | `698.310` | `68.269` | `43.534` | pass |

Readout:

- control mean prefill: `702.605 tok/s`;
- candidate mean prefill: `947.589 tok/s`;
- uplift: `+34.87%`;
- no output hash change; no cached tokens; exact JSON validation passed.

Artifacts:

- `data/gemma4-long-context-service-gate-20260630Tfattn-gqa8-controlA.json`
- `data/gemma4-long-context-service-gate-20260630Tfattn-gqa8-candidateA.json`
- `data/gemma4-long-context-service-gate-20260630Tfattn-gqa8-candidateB.json`
- `data/gemma4-long-context-service-gate-20260630Tfattn-gqa8-controlB.json`

## Broad Long-Context Service Gate

Command:

```bash
GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8 \
STAMP=20260630Tfattn-gqa8-broadA \
LONG_CONTEXT_CASE_IDS='lc-12288-early lc-16384-late lc-22000-middle' \
LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS=24000 \
LANE_SPECS='0:1024:1024:ub1024-gqa8 1:2048:2048:ub2048-gqa8 2:2304:2304:ub2304-gqa8 3:2560:2560:ub2560-gqa8' \
CANARY_REPEATS=2 MAX_TOKENS=96 BASE_PORT=18520 \
repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh
```

Cases:

- `lc-12288-early`: `16213` actual prompt tokens;
- `lc-16384-late`: `22730`;
- `lc-22000-middle`: `30400`.

All lanes passed:

- long-context gate passed;
- exact JSON validation passed every row;
- `cached_tokens=0` every row;
- canary passed every lane.

Summary:

| Config | Median prefill tok/s | Median decode tok/s | 30400-token prefill tok/s | Decision |
|---|---:|---:|---:|---|
| UB1024 | `969.770` | `125.358` | `892.338` | best decode balance |
| UB2048 | `1039.603` | `119.083` | `950.010` | balanced service candidate |
| UB2304 | **`1075.983`** | `116.999` | **`964.759`** | best pure prefill |
| UB2560 | `1066.029` | `116.496` | `963.876` | tie-ish with UB2304, lower median |

Artifact:

- `data/gemma4-long-context-service-gate-20260630Tfattn-gqa8-broadA.json`

## Short-Decode Guards

The patch is not a short-decode record. It must not replace the promoted
`123.67689864739785 tok/s` LocalMaxxing recipe.

Mixed short guard:

```bash
GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8 \
STAMP=20260630Tfattn-gqa8-shortguardA \
LANE_SPECS='0:1024:1024:ub1024-gqa8-a 1:1024:1024:ub1024-gqa8-b 2:2048:2048:ub2048-gqa8 3:2304:2304:ub2304-gqa8' \
CANARY_REPEATS=32 MAX_TOKENS=512 BASE_PORT=18540 \
repro/gemma4-26b-a4b-q8-b70/run-vdr2-short-decode-guard.sh
```

Result:

- all lanes passed the fixed cold realistic gate;
- all rows had `cached_tokens=0`;
- canary passed `128/128` per lane;
- medians:
  - UB1024 average `116.841 tok/s`;
  - UB2048 `122.130 tok/s`;
  - UB2304 `110.969 tok/s`.

Focused UB1024 A/B:

```bash
# Control lanes.
STAMP=20260630Tfattn-gqa8-short-controlB \
LANE_SPECS='0:1024:1024:ub1024-control-a 1:1024:1024:ub1024-control-b' \
CANARY_REPEATS=32 MAX_TOKENS=512 BASE_PORT=18540 \
repro/gemma4-26b-a4b-q8-b70/run-vdr2-short-decode-guard.sh

# Candidate lanes.
GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8 \
STAMP=20260630Tfattn-gqa8-short-candidateB \
LANE_SPECS='2:1024:1024:ub1024-gqa8-a 3:1024:1024:ub1024-gqa8-b' \
CANARY_REPEATS=32 MAX_TOKENS=512 BASE_PORT=18540 \
repro/gemma4-26b-a4b-q8-b70/run-vdr2-short-decode-guard.sh
```

Result:

- controls: `118.631`, `122.399` tok/s, average `120.515`;
- candidates: `118.999`, `118.448` tok/s, average `118.724`;
- all lanes valid, `cached_tokens=0`, canary passed.

Readout:

- no LocalMaxxing submission;
- no short-record promotion;
- keep the short record recipe unchanged;
- for a single service recipe, prefer UB2048 as the balanced setting;
- for pure long-prefill service where short decode is not the active metric,
  UB2304 is the best prefill setting seen so far.

## Decision

Promote the source patch and `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8` as a
validated **Gemma 4 Q8 service/prefill** optimization.

Do **not** submit it as a short-decode LocalMaxxing record:

- it did not beat `123.67689864739785 tok/s`;
- UB1024 short A/B showed normal valid variance, not a headline win;
- service/prefill rows are intentionally separate from the fixed realistic
  short-decode record policy.

Next useful work:

- consider a default-on guarded upstreamable version only for the exact
  `DV=512`, GQA8 Gemma/B70 shape after more model coverage;
- test the second audit idea, a default-off mask pre-scan threshold, but keep
  it subordinate to this confirmed GQA8 tile win;
- if one server must serve both short-record and long-prefill traffic, consider
  the separate runtime patch for phase-specific prefill/decode ubatch; launch
  flags alone cannot do that today.
