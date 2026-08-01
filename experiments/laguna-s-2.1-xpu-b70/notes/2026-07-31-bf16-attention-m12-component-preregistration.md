# Laguna BF16 attention native-M12 component preregistration

Date: 2026-07-31 America/Toronto

Status: **repeated- and streamed-weight component gates passed; one frozen
candidate endpoint is authorized; no endpoint throughput is yet claimed**.

## New evidence and bounded premise

The exact current-record target profile on vLLM `50bf5df1` and kernel
`8dd94f2` places 64.9--69.8% of the first target replay in captured graph
segments. On the slowest rank, the two graph slots surrounding attention
consume 28.645 and 27.442 ms of the perturbed 130.573 ms replay, comparable to
the 34.028 ms post-attention/MoE slot.

Laguna's target QKV and O projections are unquantized BF16. Exact speculative
verification currently presents width 12 as a stride-zero batch of twelve
independent M=1 GEMMs. The existing native-MM treatment was tested only at
width 8. It passed extensive raw bitwise gates but regressed the old depth-7
endpoint by 3.4--3.8%; its hot component timing was misleading. That result
remains valid and is not erased.

Width 12 is new evidence only because it changes the exposed M dimension and
can select different oneDNN geometry. This authorizes a cheap component screen,
not a model retry of the old failed idea.

## Screen

Extend the existing `gate_laguna_bf16_attention.py` with an explicit `--rows`
argument whose default remains eight. On one healthy B70, compare literal
stride-zero BMM with native `torch.mm` at rows 12 for the four physical target
projection shapes:

- full QKV: K=3072, N=2048;
- sliding QKV: K=3072, N=2816;
- full O: K=1536, N=3072;
- sliding O: K=2304, N=3072.

Run at least 16 independently seeded input/weight epochs per physical shape
and require raw BF16 equality, including each Q/K/V slice. The logical-only
Q/K/V diagnostic shapes may be retained but cannot justify promotion.

The existing repeated-weight timing is L3-hot and may only reject a candidate;
it cannot promote one. If exactness passes and hot timing is promising, a
second component must cycle the actual 12-full/36-sliding layer weight families
so weights are streamed rather than repeatedly reused. Endpoint consideration
requires that streamed component to beat stride-zero BMM materially and on
both QKV and O aggregates. A hot-only win is closed by the M=8 history.

## Stop conditions

Stop without source integration or a model run if any physical output differs,
if native M12 loses the repeated-weight screen, if the streamed-weight result
does not improve both projection aggregates, or if the honest projected gain
is below the endpoint noise floor.

The component stage authorizes no KV/model/draft precision change, arithmetic
relaxation, teacher change, benchmark metric change, reset, reboot, or
LocalMaxxing submission. A service launch becomes authorized only by the
explicit integration section below after both component gates pass.

## Component results

Artifact:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
laguna-bf16-attention-m12-component-20260801T024524Z
```

The original changed-input gate at rows 12 passed `224/224` raw-BF16 checks.
The four physical projection shapes were each 25--27% faster in the
repeated-weight timing. This result alone did not authorize integration.

The streamed gate then allocated the actual 12-full/36-sliding sequence of 48
distinct weights per family and ran ten interleaved samples of four complete
passes per arm:

| family | working set | raw exact | stride-zero BMM | native M12 | speedup |
| --- | ---: | ---: | ---: | ---: | ---: |
| QKV | 777,388,032 B | 48/48 | 2.432115 ms | 1.838702 ms | **1.322734x** |
| O projection | 625,287,168 B | 48/48 | 2.430738 ms | 1.834386 ms | **1.325096x** |

Both families are far larger than device cache, both arms use identical
inputs and weights, the arm order alternates by sample, and every individual
sample preserves the same ordering. The combined component saving is about
1.190 ms per target forward.

## Integration authorization

vLLM source `f5cdc7401d623bc510734e304f1da782a022f620` changes only the existing
default-off native-BF16-attention selector's row gate from exactly 8 to
`{8,12}`. It retains the exact-target marker, exact-spec-attention requirement,
BF16 input/weight requirement, verifier-row requirement, and the four physical
shape allowlist. Draft, gate projection, prefill, M=1 fallback, quantized
linears, and every selector-off call remain unchanged.

The measurement leg exposes the treatment only as optional literal argument
37, records it in identity, and verifies the service environment. One fresh
cold candidate on the exact 122.829 BF16-KV record identity is authorized.
Require 13/13 token and text exactness, all cached-token counts zero, target
146/145 and draft 14/13 on all four ranks, one suite invocation, no warmup or
retry, and clean teardown. A failure yields no quoted rate. A pass may be
compared with the confirmed 122.829 record, while any small delta still
requires an independent confirmation before promotion.
