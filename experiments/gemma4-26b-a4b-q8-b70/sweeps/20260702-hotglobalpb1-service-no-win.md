# Gemma 4 26B Q8 Hot Global FlashAttention PB1 Service Screen

Date: 2026-07-02

## Question

After the service node profile showed the remaining prompt-processing hotspot
inside full/global FlashAttention, Boyle audited the current SYCL tile path and
found one bounded scheduler experiment that had not been tested in this narrow
form: force `parallel_blocks=1` only for the profiled hot global GQA8 shape.

The broad prior knob `GGML_SYCL_FATTN_PARALLEL_BLOCKS=1` was closed as a bad
tradeoff because it improved prefill only slightly and collapsed long-context
decode. This experiment tested a much narrower default-off source gate:

```bash
GGML_SYCL_FATTN_DV512_GQA8_GLOBAL_PB1=1
```

The candidate matched only the service global-GQA shape:

- `DV == 512`;
- `ncols1 == 2`, `ncols2 == 8`;
- `nbatch_fa == 64`;
- mask present, `KV_min == nullptr` so SWA-local attention is excluded;
- `Q->ne[1] == 2`, `Q->ne[2] == 16`, `Q->ne[3] == 1`;
- `K->ne[1] == 256`, `K->ne[2] == 2`, `K->ne[3] == 1`;
- `Q/K` head dimension `512` or `576`, `V` head dimension `512`.

## Patch And Build

Pre-edit source snapshot:

- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-hotglobal-pb1-preedit-source.patch`
- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-hotglobal-pb1-preedit-source.diffstat`

Tested source patch:

- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-hotglobal-pb1-source.patch`
- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-hotglobal-pb1-source.diffstat`

Reusable reproduction wrapper:

- `repro/gemma4-26b-a4b-q8-b70/run-vdr2-hotglobalpb1-service-confirm.sh`

Build command:

```bash
cd /home/steve/src/llama.cpp-gemma-record-repro-c926
source /opt/intel/oneapi/setvars.sh --force
cmake --build build-sycl-b70-aot-bmg-g31-q8reorder-vdr2 --target llama-server -j 8
```

The test build completed. After the no-win decision, the source patch was
reverted exactly:

```text
git diff | sha256sum
7220e022ae836b2a885f6e1ba5d73422f1ddd9c74e0c3e4582a0d7066fa295e3  -
```

The baseline binary was rebuilt. Restored `libggml-sycl.so.0.15.2` hash:

```text
61c364b690ea6f852ad71c77abd65605c33de967dc9186c19d322c28e4ea8864
```

## Smoke

Candidate-only one-case smoke:

- summary: `data/gemma4-long-context-service-gate-20260702Thotglobalpb1-smoke1.json`
- run dir:
  `data/gemma4-q8-gpu0-longctx-pb1-smoke-gpu0-ctx32768-o96-20260702Thotglobalpb1-smoke1/`
- case: `lc-12288-early`;
- exact JSON validation passed;
- canary passed;
- `cached_tokens=0`;
- approximate prefill `1223.293322173528 tok/s`;
- after-TTFT decode `127.80984727548336 tok/s`;
- TTFT `13.253566995030269 s`.

## Four-GPU A/B + Crossover

The full screen compared the current service stack plus the existing KQ
register/broadcast service flag against that same stack plus PB1:

- control: `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8`,
  `GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST=1`,
  SWA left-bound `MIN_Q=2048`;
- candidate: control plus `GGML_SYCL_FATTN_DV512_GQA8_GLOBAL_PB1=1`;
- one replica per B70 GPU, GPUs 0-3;
- four waves so every GPU saw both control and candidate twice;
- cases: `lc-12288-early`, `lc-16384-late`, `lc-22000-middle`;
- `MAX_TOKENS=96`, `CANARY_REPEATS=2`;
- all 48 records passed exact JSON validation and `cached_tokens=0`.

Evidence:

- comparison:
  `data/gemma4-global-fattn-hotglobalpb1-comparison-20260702Thotglobalpb1-service-ab1.json`
- wave summaries:
  - `data/gemma4-long-context-service-gate-20260702Thotglobalpb1-service-ab1-waveA-control.json`
  - `data/gemma4-long-context-service-gate-20260702Thotglobalpb1-service-ab1-waveA-candidate.json`
  - `data/gemma4-long-context-service-gate-20260702Thotglobalpb1-service-ab1-waveB-control.json`
  - `data/gemma4-long-context-service-gate-20260702Thotglobalpb1-service-ab1-waveB-candidate.json`
  - `data/gemma4-long-context-service-gate-20260702Thotglobalpb1-service-ab1-waveC-control.json`
  - `data/gemma4-long-context-service-gate-20260702Thotglobalpb1-service-ab1-waveC-candidate.json`
  - `data/gemma4-long-context-service-gate-20260702Thotglobalpb1-service-ab1-waveD-control.json`
  - `data/gemma4-long-context-service-gate-20260702Thotglobalpb1-service-ab1-waveD-candidate.json`

Aggregate result:

| metric | control mean | candidate mean | mean delta | control median | candidate median | median delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| approximate prefill tok/s | `1123.309` | `1124.450` | `+0.102%` | `1129.954` | `1132.893` | `+0.260%` |
| after-TTFT decode tok/s | `120.598` | `120.750` | `+0.126%` | `120.470` | `120.766` | `+0.246%` |
| TTFT seconds | `21.040` | `21.021` | `-0.091%` | `20.116` | `20.064` | `-0.259%` |

Same-GPU prefill deltas were all positive but tiny:

| GPU | prefill delta | decode delta | TTFT delta |
| --- | ---: | ---: | ---: |
| 0 | `+0.074%` | `+0.086%` | `-0.084%` |
| 1 | `+0.133%` | `+0.004%` | `-0.139%` |
| 2 | `+0.145%` | `+0.135%` | `-0.107%` |
| 3 | `+0.055%` | `+0.280%` | `-0.034%` |

Same-case prefill deltas were also positive but tiny:

| case | prefill delta | decode delta | TTFT delta |
| --- | ---: | ---: | ---: |
| `lc-12288-early` | `+0.118%` | `+0.100%` | `-0.118%` |
| `lc-16384-late` | `+0.125%` | `+0.130%` | `-0.125%` |
| `lc-22000-middle` | `+0.056%` | `+0.152%` | `-0.057%` |

Wave direction still dominated the raw per-wave result:

| wave | prefill delta | decode delta | TTFT delta |
| --- | ---: | ---: | ---: |
| A | `-0.666%` | `-0.412%` | `+0.707%` |
| B | `+0.907%` | `+0.551%` | `-0.905%` |
| C | `-0.817%` | `-0.198%` | `+0.862%` |
| D | `+0.997%` | `+0.569%` | `-1.015%` |

## Decision

**No win / do not promote.**

The narrow PB1 gate is valid, but the measured benefit is only about
`+0.10%` mean prefill / `+0.26%` median prefill on top of the current service
stack, below the service promotion threshold and far below what is worth
carrying as another source flag. The small same-GPU and same-case positives are
not enough to overcome the wave-placement noise.

Do not submit this to LocalMaxxing. It is service/prefill-only and did not
materially improve the current validated service recipe. Do not retest broad
`PARALLEL_BLOCKS=1`; that route remains closed because of the prior decode
collapse. Future global FlashAttention service work needs a structural tile or
scheduling redesign, not another static one-pass override.
