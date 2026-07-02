# Gemma 4 26B Q8: accept-prefix top1 epilogue verifier negative

Date: 2026-07-02

Status: closed negative. Do not promote, submit, or retest unless the verifier
design changes materially.

## Purpose

Test `LLAMA_SYCL_ACCEPT_PREFIX_TOP1_EPILOGUE=1` together with
`LLAMA_SPEC_VERIFY_ACCEPT_PREFIX_ARGMAX=1`.

The idea was to keep the exact device-side accept-prefix dependency from the
previous accept-prefix verifier path, but replace the per-row scratch reduce
with the reordered Q8_0 top1 epilogue. This preserved target-model verification
and did not use prompt/cache/history reuse.

## Artifacts

- Preedit source snapshot:
  `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-acceptprefix-epilogue-preedit-source.patch`
- Tested source snapshot:
  `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-acceptprefix-epilogue-source.patch`
- Parity smoke:
  `data/gemma4-q8-gpu0-acceptprefix-epilogue-parity-smoke-20260702Tacceptprefixepi01/summary.json`
- Four-lane A/B:
  - controls:
    `data/gemma4-q8-gpu0-acceptprefix-epilogue-ab-control-20260702T105620Z/summary.json`,
    `data/gemma4-q8-gpu2-acceptprefix-epilogue-ab-control-20260702T105620Z/summary.json`
  - candidates:
    `data/gemma4-q8-gpu1-acceptprefix-epilogue-ab-candidate-20260702T105620Z/summary.json`,
    `data/gemma4-q8-gpu3-acceptprefix-epilogue-ab-candidate-20260702T105620Z/summary.json`

After the test, the active source checkout was restored to the preedit diff
exactly (`git diff` SHA-256 matches the preedit patch:
`7220e022ae836b2a885f6e1ba5d73422f1ddd9c74e0c3e4582a0d7066fa295e3`).
The rebuilt promoted binary returned to the expected SYCL library hash:
`libggml-sycl.so.0.15.2 = 61c364b690ea6f852ad71c77abd65605c33de967dc9186c19d322c28e4ea8864`.

## Validity

All four A/B lanes passed the fixed realistic cold gate:

- `cached_tokens=0` for every request;
- each prompt was unique and run once;
- canary passed (`64/64` rows per lane);
- `realistic_final_gate.passed=true`;
- target/verifier and quantization unchanged (`UD-Q8_K_XL` target, Q4_0 MTP
  draft accepted only after target verification).

These are valid diagnostics, but not LocalMaxxing candidates because they are
below the current valid `124.97714084813418 tok/s` Gemma Q8 record.

## Results

Primary metric: median generated-token throughput for tokens 1-100 after TTFT.

| lane | GPU | flags | median tok/s | p10 | mean |
|---|---:|---|---:|---:|---:|
| control | 0 | none | `116.016230` | `105.926307` | `118.015874` |
| candidate | 1 | `ACCEPT_PREFIX_ARGMAX=1`, `ACCEPT_PREFIX_TOP1_EPILOGUE=1` | `106.254888` | `99.730729` | `106.941242` |
| control | 2 | none | `116.980569` | `108.071021` | `118.330842` |
| candidate | 3 | `ACCEPT_PREFIX_ARGMAX=1`, `ACCEPT_PREFIX_TOP1_EPILOGUE=1` | `103.904324` | `98.281511` | `106.285311` |

Mean of per-lane medians:

- controls: `116.498399 tok/s`;
- candidates: `105.079606 tok/s`;
- delta: `-11.418793 tok/s`, `-9.80%`.

The parity smoke also passed (`64/64`, fixed realistic gate passed,
`cached_tokens=0`) but was similarly slow at `110.191660 tok/s`.

## Decision

Closed negative. The top1 epilogue removed the scratch reduce, but the
row-by-row accept-prefix dependency still serializes verifier work and adds
launch overhead. It is materially slower than the promoted baseline.

Future short-decode verifier work should not repeat row-by-row accept-prefix
variants. The remaining plausible verifier lever is a deeper backend/graph
design that avoids unnecessary verifier output rows without serial launches:
candidate-bound LM-head / compact argmax, head-only bonus while preserving the
bonus pipeline, or a verifier MoE boundary reduction.
