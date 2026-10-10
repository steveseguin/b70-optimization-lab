# Packet 4 preparation: eager fixture transport and CPU replay

2026-10-10. **NOT READY for native extraction: source-bound boundary hooks
are implemented and CPU-tested; complete U-row extraction is still blocked.**
The [adapter](adapters/vllm_xpu_certified.py) maps 44 callable symbols with
exact input/output selectors, state locations, dtype expectations, source
lines and SHA256s in [names.json](adapters/names.json). It observes the original
call once, preserves its result object, and restores methods in `finally`.
This is comparator instrumentation, not code for our inference runtime.

The [source receipt](adapters/source-extraction.json) records stopped-container
copies of the locally present reopen image, its installed package and extension.
Neither container was started; both were removed. The image has no baked A367
patch set; its extension hash differs from the rebuilt A367 extension. All 75
tracked A367 seal members matched. Flash mappings therefore use a scratch
`git archive` of certified host commit `6d872457`; image file hashes are
reported separately. The 27B package image was absent and was not pulled;
its 16 mappings describe the reopen image's 27B graph, **not a certified 27B
comparator**. No extracted runtime source or binary is committed.

| Stage 1 census row | Symbols mapped |
| --- | ---: |
| U1 FP8/linear | 4 |
| U2 parameter/embedding boundaries | 4 |
| U3 norm/activation/HC | 9 |
| U4 recurrence/conv state | 6 |
| U5 attention/RoPE/QSA | 12 |
| U6 logits/router/tie dispatch | 5 |
| U7 MTP boundaries | 5 |

Counts overlap: 45 row memberships across 44 symbols. `stage2_u_rows` keeps
Flash's differently numbered census separate. These counts describe source
coverage, not observed native fixtures or passed quality gates.

**66 CPU tests pass: 27 adapter checks plus 39 existing transport checks, zero skips.**
All 44 source symbols passed the AST/hash check without importing vLLM.
[Adapter CPU receipt](test-receipt-adapter.json),
[original transport receipt](test-receipt.json),
[historical environment audit](comparator-identity-audit.json),
[remaining work and conditional window](WINDOW-RUNBOOK.md).

### Exact remaining work

1. Admit the A367 host environment or separately qualify a container; obtain
   the 27B certified source/overlay binding. The reopen image is not either
   certified comparator, despite sharing many names.
2. Supply the native worker session with actual CPU scheduler row positions,
   valid masks, layer/rank/M/N/K, bounded touched state/KV and PLE row views,
   per-rank writers, final token collection and cooperative teardown. The
   adapter's `run(args, Recorder)` intentionally refuses until that session
   driver exists. `install()` is a working in-process hook registration API,
   not a completed CLI model runner.
3. U1 needs fused oneDNN and Flash FP8 quantization evidence; U2 needs the
   complete post-load parameter/cast census. U3/U5 need fused norm/gate and
   QSA pre-indexer intermediate evidence. Python boundary hooks cannot expose
   values a fused operator does not materialize.
4. U4 needs every internal serial GDN row state/checkpoint and accepted-prefix
   replay; U7 needs acceptance/rollback state bindings. Before/after snapshots
   of an outer call do not replace these. Keep Flash inter-row state BF16 and
   27B state FP32. Never split or replace a fused op to manufacture fixtures.
5. Bind native layouts to independent CPU reference calls. The current adapter
   deliberately writes raw boundaries with `reference=null`; comparison stays
   UNTESTED. Execute U6 tie/NaN, full vocabulary, MoE top10/EP and PLE-row gates,
   eager neutrality and full same/fresh-process token repeats. Natural M6
   availability and the current host halt/window authorization remain gates.

### CPU source validation and worker interface

The standalone AST checker imports neither torch nor vLLM. Its roots are
scratch directories containing `vllm/`, never an active runtime checkout:

```bash
nice -n 19 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage1/packet4-prep/adapters/check_sources.py --a367-root "$A367_SOURCE" --image-root "$IMAGE_SOURCE"
nice -n 19 env OMP_NUM_THREADS=2 PACKET4_A367_SOURCE="$A367_SOURCE" PACKET4_IMAGE_SOURCE="$IMAGE_SOURCE" /home/steve/.venvs/vllm-xpu/bin/python -B experiments/own-xpu-runtime/stage1/packet4-prep/run_tests.py
```

A future worker must enter `eager_guard` before constructing any model or
caching `CustomOp` bound methods, then enter `install` with exact resolved
owners and source roots. The guard blocks Torch XPU/CUDA graph entry and the
vLLM graph wrapper without querying a device. The hook checks eager/compile
configuration before metadata callbacks or tensor reads. Previously captured
graphs or cached capture aliases are outside this contract: use a fresh worker.
No hooks may be installed into a running compiled model. Registered custom
operators are intercepted at their exact `torch.ops.vllm` alias, with their
schema checked; patching their original Python function would miss dispatch.
`install` validates all selected symbols before installation and rolls back on
failure. Stateful observations refuse absent touched-state bindings. Hook
selection and unvisited symbols must be reported; a subset is diagnostic only.

## The comparator identity discrepancy

The [A367 guide](../../../../repro/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913/README.md)
records **46.854250 tok/s in a host venv**, with torch 2.11.0+xpu,
Triton 3.7.0, vLLM overlay `6d872457` and the hybrid `bbae3c5` kernel stage.
It explicitly says its container route was unbuilt and unadapted. There is no
certified A367 image digest to put in an honest launch command.

The October reopen image is
`vllm/vllm-openai-xpu@sha256:e4446310b1d30015e8fdc1a0a2ef1669ac6bef857cbe772487571ed5c1a926a9`.
Its sealed overlay is a different code line; full-model loading and generation
remain unqualified. The audit pins both sets of evidence and hashes the five
A367 patch-series seals. It never equates the October image with A367.
`audit_identity.py` rebuilds this audit using repository files only.

## Tool contracts

`extract_fixtures.py` exposes `Recorder.hook` for torch modules and
`Recorder.monkeypatch`/`observe` for functions and in-place operators. Each
original call executes exactly once; hooks return no replacement and the
monkeypatch returns the original result. Inputs and touched state are written
before the call, outputs and committed state afterward. Hook removal uses
`finally`. There is no native runtime import or model construction in this
tool. A separately reviewed driver must own those responsibilities.

The driver supplies normalized arguments, observed output views, touched state
views, layer/rank, actual M/N/K, row indices, positions, padding validity,
dispatch/cast description and CPU reference mappings. It must not compute a
surrogate output, read a device scalar to choose a view, scan a whole state
pool or split a fused operator to expose an internal intermediate. Source-only
metadata determines those views. An internal value that a fused operator never
materializes is **unobservable by these hooks**; record that gap instead of
replacing the operator. TP4 requires one recorder per worker with rank-specific
directories and a shared total budget divided among all four writers.

The recorder admits eager execution only: eager=true, compile=NONE,
graph=NONE, prefix cache=false, no enabling graph environment variable, and no
active torch compilation. The driver must derive that configuration from the
actual engine and install `forbid_graph_entrypoints` on the pinned torch/vLLM
capture entry points **before constructing the engine**. A supplied config
dictionary alone is not proof that an arbitrary native runtime obeys it.
The dummy entry-point refusal and restoration are CPU-tested; source adapter blocks the graph wrapper and Torch capture APIs in CPU tests;
fresh-worker native integration remains pending.

Tensor storage is raw little-endian, with SHA256, dtype, shape, stored strides,
offset and byte count. Original view layout is retained separately. Scalars
store as one-element arrays; broadcast and noncontiguous views store logical
contiguous values. D2H copies are blocking chunks, default 1 MiB, maximum
16 MiB; only a few chunks can be live, with no background queue or retained
tensor archive. Metadata, provenance and tensors all consume `--max-bytes`.
The cap is checked before tensor transfer. A cap failure leaves partial evidence
without a successful extraction receipt; it does not skip data and claim
completion. Exceptions return to the driver's cooperative shutdown, never a
forced process exit. Reusing an output directory is refused.

`finish` compares the entire observed token array with the selected authenticated
oracle array and requires cached_tokens=0. A mismatch saves a rejected receipt
and raises. This proves only the selected prompt, not all twelve outputs or
same/fresh-process repeat neutrality. An eager-only mismatch with the old
graph-enabled oracle is a failed diagnostic, not permission to weaken the oracle.

The emitted v2 schema is a documented extension of the unchanged
[v1 envelope](../packet1b/tests/fixture-extraction.schema.json), whose hash is
embedded. It adds Flash operators, row/rank/call information, nullable image
identity for the actual host comparator, and single-prompt diagnostics. The
twelve **oracle** hashes are separate from measured full-suite hashes (empty).
Unperformed repeats point to a real hashed pending receipt. `qualified` is
forbidden in v2. Every bundle saves its exact schema and extractor bytes.
Integer-only PLE metadata may be in the reference call rather than tensor inputs.

`compare_fixtures.py` validates envelopes, artifact hashes, lengths, dtype,
canonical strides, path containment, oracle arrays and reference code hashes.
It uses private CPU mmap views, never pickle or device loads. It dispatches to
the existing Stage 1/Stage 2 references through an explicit function allowlist.
Declarative `$linear`, `$bank`, `$rows` and `$call` descriptors support their
linear/expert/PLE/attention-block callable dependencies without serializing code.
Unknown functions/layouts or missing output/state mappings remain UNTESTED.

Reports contain per-tensor bit equality, different-element count, first index,
maximum absolute difference and maximum ordered-bit ULP distance. Integer
differences cannot overflow I64. Signed zero is not bit-exact; unequal NaN/Inf
pairs report nonfinite differences rather than a tolerance pass. Shape/dtype
mismatches remain differences. Each U-row has VERIFIED-EXACT, VERIFIED-DIFF or
UNTESTED **for the recorded samples**, plus an unconditional UNTESTED full
qualification field, observed/missing M values and detailed difference links.
An empty/missing family cannot qualify; a passing subset never closes a U-row.

## What the synthetic tests cover

The small torch CPU module graph exercises 27B FP8/excluded linears, norm,
activation, convolution, recurrent state, rotary, residual, attention gate,
argmax and draft projection; Flash adds QSA pooling/selection, router, HC
combine, PLE hash/history and row lookup. There are **33 27B and 42 Flash
recorded boundaries** across outer M1/M2/M6 graphs. GDN uses the references'
real 16/48 heads and K/V128; other matrices are deliberately small. The conv
mock processes the first row, and its M labels the containing mock graph.

The mock calls the existing references to test transport and classification,
so this is **not independent mathematical validation**. Its tokens derive from
the graph output; its twelve-row synthetic oracle is marked mock and never
accepted by the native CLI. Full attention/QSA, full FFN/MoE/HC mixers, full
MTP, every intermediate row state, transactional rollback, distributed
collectives, real model weights and real prompts are **not** covered by this
mock. The replay API supports existing full reference functions, but native-to-reference normalization is still missing from this adapter. Neither reference implements
every U-row behavior (notably Flash Triton FP8 quantization and PLE injection).

Tests also alter a recorded output with a correctly refreshed SHA to prove
VERIFIED-DIFF, corrupt hashes to prove rejection, check missing mappings and
shapes, and exercise state snapshots, graph refusal, byte limits, signed
zeros, nonfinite values, hook restoration, token mismatches and cache hits.
All scratch uses automatically removed temporary directories. Re-run:

```bash
nice -n 19 env OMP_NUM_THREADS=2 /home/steve/.venvs/vllm-xpu/bin/python -B experiments/own-xpu-runtime/stage1/packet4-prep/run_tests.py
```

To write a new receipt add `--receipt PATH`. The command-line mock and replay
are also available; use a newly created parent directory and delete only your
own synthetic output after reviewing it:

```bash
nice -n 19 env OMP_NUM_THREADS=2 /home/steve/.venvs/vllm-xpu/bin/python -B experiments/own-xpu-runtime/stage1/packet4-prep/extract_fixtures.py --mock --model flash-next --output /tmp/packet4-example/fixtures --max-bytes 536870912
nice -n 19 env OMP_NUM_THREADS=2 /home/steve/.venvs/vllm-xpu/bin/python -B experiments/own-xpu-runtime/stage1/packet4-prep/compare_fixtures.py /tmp/packet4-example/fixtures --output /tmp/packet4-example/comparison.json
```
