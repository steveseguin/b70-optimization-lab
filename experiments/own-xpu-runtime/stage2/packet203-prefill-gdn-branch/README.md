# Packet203: synthetic GDN normalization, output and stream injection

## Question and identity

Does adding the missing gated normalization, output projection and four-stream
injection preserve the two-row branch-core result from packet202? The fixture
uses synthetic weights/inputs and the current selected production-derived CPU
arithmetic. It connects those missing operations; **alpha/beta and HC injection
controls remain synthetic inputs**, as in packet202. Their upstream projections,
HC processing, FFN, QSA, full-model scheduling and cache policy are not qualified.
No device, model, native owner, endpoint or service is started.

## Outcome

The [CPU differential](evidence/host-differential.json) passes five cases with
nine byte comparisons each. Five stages recheck the immutable packet202
qkv/z/convolution/GDN/state result. Four new stages compare gated BF16 output,
all split scratch bytes, BF16 output projection and all four streams of both
rows. Each case also demonstrates that zeroing z changes the result, omitting
injection changes it, changing each of eight injection values affects its stream,
and injecting the unrounded FP32 projection changes final bytes.

This is an executable CPU exactness result, not a device speed, cache reuse,
full-branch operator qualification or live-admission claim.

## What worked

[Production binding](production-binding.json) fixes the actual p201 identity:
Q6_K output projection K6144→2560, variant7 `expanded_split4_v1`, four SG32
partial trees, expanded stride8112B and20,766,720B resident weights. Synthetic
packed Q6 is expanded by the frozen transform. Normalization uses128-wide
heads,128 F32 gains, flags8, then sigmoid(z), with only the final BF16 store.

The serial norm runs the selected `p42tiny::cooperative_group<gated_norm>`
statement-body mirror once per row. The candidate uses the frozen two-row
`ng::cpu` form; equality here does not establish SYCL compilation or launch
geometry. Serial output calls the actual pinned
`p49c::DenseKernel<Q6_K,6144,4,attention_combine>::run`; separate pinned lane
calls expose each private FP32 partial for comparison. The candidate uses two
independent ordered accumulators sharing decoded weights, then the original
`(p0+p1)+(p2+p3)` sum, **BF16 projection**, widened projected value and four
stream updates. It retains eight-float scratch stride, checking four live
partials and four unchanged sentinel slots per output row.

The immutable packet202 fixture is included with its `main` renamed solely to
reuse synthetic generators and branch-core functions. No packet202 source is
changed. The new tail validates all operand/output extents and actual address
ranges, including a refusal test that aliases a real output vector with an
input. Model weights are never read.

## Guard boundary and limitations

`finish_branch` adds a **fixture tail-entry admission policy**: inactive or
sticky-error calls preserve all tail outputs; invalid start/count sets sticky
error and preserves those outputs. Position and active controls remain intact.
The `--binding-check` proof tests this entry policy, not raw selected-operator
inactive intermediate parity.

The underlying selected p49c operator intentionally writes projected y (and
its device partial scratch) even when inactive/error is set; only stream
injection is guarded. Its attention-tail `position_valid` returns true.
Packet203 does not change those native semantics or claim that the device
kernel owns the new entry check. Any later integration must retain the explicit
entry admission and separately account for raw operator behavior. Normal active
byte parity alone does not prove an untested native failure path.

No numerical or compilation failure occurred. The first passing attempt only
proved that omitting injection differed; independent review requested a stronger
input-control test. The final attempt perturbs every injection value and checks
all eight stream segments. Both attempts preserve exact source and raw results.
The first receipt's broader short scope label is superseded by the explicit
synthetic alpha/beta and HC-control boundary in the final receipt and this note.

## Reproduction and evidence

From the repository root:

```bash
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 \
  nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/stage2/packet203-prefill-gdn-branch/build_engine.py --run
```

This builds a synthetic `OWN_RT_HOST_ONLY` executable with GNU C++20, no fast
math, disabled FP contraction, the existing compiler-turn lock, helper cores,
nice19 and a4GiB address-space ceiling. It neither links nor launches a device
runtime. Source and binary hashes are checked after compilation and execution;
[build.json](evidence/build.json) binds the compiler-discovered repository
closure, including packet202. Original source/compile log and differential
stdout/stderr are retained per attempt. `build/` is ignored.

The top-level bridge uses repository-relative includes. Inherited sealed
headers retain historical absolute includes, so this currently reproduces in
`/home/steve/llm-optimizations`; it is not a portable package claim. The separate
[authority map](AUTHORITY.md) records selected source/metadata provenance.
Planner/authority tests consume the saved numerical receipt and current hashes,
and execute only the bounded guard modes instead of repeating numerical work.

## When to revisit

Use this proof as a frozen regression baseline before adding missing alpha/beta
projection authority, HC/layer coverage or causal QSA/PLE. Full integration still
needs row binding/lifetime and cache-cadence design, all-layer state checks,
resource admission and a separately authorized device gate. No new operational
window is proposed by this packet.
