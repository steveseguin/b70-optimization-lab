# Packet 4 preparation: eager fixture transport and CPU replay

2026-10-10. **CPU mock tests pass; native extraction is not ready.** This
packet supplies working read-only hooks, streamed tensor storage, reference
replay and failure classification. It does **not** supply a source-bound vLLM
operator/state adapter. In particular, it cannot yet extract all U1–U7 from a
real model. That is an outstanding part of the requested deliverable, not a
passed gate. No device, server, systemd unit, model payload or port was used.

[Tests and source hashes](test-receipt.json), [environment audit](comparator-identity-audit.json),
[window commands and remaining admission work](WINDOW-RUNBOOK.md).

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
The dummy entry-point refusal and restoration are CPU-tested; real capture
entry-point bindings have not been supplied or tested.

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
mock. The replay API supports existing full reference functions, but their
native normalization bindings remain absent. Neither reference implements
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
