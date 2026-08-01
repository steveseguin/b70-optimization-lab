# Laguna BF16 attention native-M12 component preregistration

Date: 2026-07-31 America/Toronto

Status: **component-only screen authorized; no model endpoint or throughput
claim authorized**.

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

No KV/model/draft precision change, arithmetic relaxation, teacher change,
benchmark metric change, reset, reboot, service launch, endpoint, or
LocalMaxxing submission is authorized here.
