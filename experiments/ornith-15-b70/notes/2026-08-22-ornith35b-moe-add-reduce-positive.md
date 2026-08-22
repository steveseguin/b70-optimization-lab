# Ornith 1.5 35B-A3B: ordered MoE add reduction

Date: 2026-08-22 EDT

Status: **accepted target-only package increment; +4.85% matched serving**

## Bottleneck and candidate

A one-token SYCL topology trace showed that the tuned routed `MUL_MAT_ID`
kernels consume only about 1.3 ms/token. The larger avoidable boundary was the
post-expert reduction: each of 40 MoE layers issued one weighted `MUL` and
seven serial FP32 `ADD` kernels to reduce eight active experts.

The lab patch keeps the weighted `MUL` unchanged and replaces only the exact
ordered seven-`ADD` chain with one kernel. Admission requires eight contiguous
FP32 expert rows, ascending view offsets, the exact accumulator dependency
chain, single-use intermediates, and a contiguous one-row destination. The
door is default off:

```bash
export GGML_SYCL_FUSED_MOE_ADD_REDUCE=1
```

Patch packet:
`../../../patches/ornith-15-35b-a3b-q4km-b70/README.md`.

## Mechanism

Over llama-bench warmup plus one measured token:

- stock `ADD` launches: `860`;
- candidate stock `ADD` launches: `300`;
- candidate fused reductions: `80`;
- net reduction: `(860 - 300 - 80) / 2 = 240` launches/token.

The GDN body itself measured only `3.14 us/layer` (`~0.09 ms/token`), and its
output-state writeback fusion was already active on all 30 recurrent layers.
Those measurements rejected GDN-body and command-graph work as the next large
decode lever.

## Performance

One B70, local directly verified model, F16 KV, flash attention, target only.

| Protocol | Controls | Candidates | Mean delta |
| --- | --- | --- | ---: |
| llama-bench `p0/n128/d0/r7` | `102.626849`, `103.468639` | `107.855830`, `108.339891` | **+4.90%** |
| fresh 12-prompt server suite | `100.239982`, `99.088182` | `104.015717`, `104.983258` | **+4.85%** |

The server metric is the median token rate for generated tokens 1-100 after
TTFT. Each of the 12 prompts was unique, executed once, and reported
`cached_tokens=0`; all four freshness gates passed.

## Correctness

- A same-binary, fixed-seed, temperature-zero, forced 400-token CLI comparison
  was byte-identical with the door off and on. Both outputs hashed to
  `08f2d1834e42656c85768beef340dda43f35a81924d24a4483613466e99056bb`.
- Candidate objective canaries passed: 8x same-server hash stability, exact
  arithmetic, exact copy, and JSON-schema output.
- Fresh stock Server A versus fresh stock Server B matched `0/12` complete
  hashes and only `5/12` 320-character previews. Cross-process response hashes
  are therefore not a valid candidate-specific exactness oracle for this
  current runtime lane. This pre-existing instability remains a limitation to
  investigate separately.

Summary:
`../data/2026-08-22-ornith35b-moe-add-reduce-summary.json`.
The four engine JSON files, four server-suite JSON files, and candidate canary
JSON are retained beside it.

## Decision and remaining headroom

Promote the patch into the Ornith 35B package with its exact base, SHA-256,
build settings, and environment door. This is a real target-only improvement,
but it is not the requested 2x. The next credible kernel boundary is the
recurrent convolution chain (`GET_ROWS -> CONCAT -> CPY -> SSM_CONV -> SILU ->
2x L2_NORM`), where our Qwen lane already demonstrated an exact fused design.
A true 2x user-visible result will probably require stacking larger launch
fusions with verified speculative decoding or a materially smaller native
quantization.
