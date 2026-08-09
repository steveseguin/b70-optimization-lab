# Q8 canonical-MMVQ component gate

This is a narrow prerequisite for the Qwen3.6 27B c2 source control. It tests
an explicitly selected GGML/SYCL runtime without loading the model and without
modifying the candidate source worktree. Candidate headers come from
`--source-dir`; shared objects independently come from the exact directory
named by `--ggml-library-dir`. This split is intentional: the authoritative
GPU gate must reproduce the study's one-DSO hybrid runtime, not an all-candidate
build that has different companion libraries.

The component uses the model-relevant Q8_0 weight shape
`[6144,5120,1,1]` and two deterministic, distinct F32 input vectors. It
requires raw F32 output bytes to match across:

- a selector-off M=1 A/B oracle in its own process;
- separate M=1 A and M=1 B operations;
- flat M=2 `[6144,2,1,1]` in both AB and BA order;
- recurrent M=2 `[6144,1,2,1]` in both AB and BA order.

There is no floating-point tolerance. Every 5,120-element output slice must be
bitwise equal to its M=1 reference.

## Fresh bootstrap orders

The launcher runs three fresh processes against independently initialized copies
of the same deterministic weight:

1. `selector-off-m1-ab`: selector-disabled M1 A, M1 B;
2. `m1-first-ab`: selector-enabled M1 A, M1 B, flat AB, recurrent AB;
3. `batched-first-ba`: selector-enabled recurrent BA, flat BA, M1 B, M1 A.

The third process makes recurrent M=2 bootstrap a virgin weight and reverses
the input order. The parent repeats all byte comparisons from retained files,
checks selector-off M1 A/B against both selector-on processes, and checks
equivalence across the two selector-on processes. All worker JSON PIDs must
match their launcher PIDs, and the three PIDs must be distinct.

## Dispatch proof

Execution is default-off and sets
`GGML_SYCL_Q8_0_C2_CANONICAL_MMVQ=1` only in sanitized child environments.
It also pins `GGML_SYCL_ENABLE_OPT=1`, `GGML_SYCL_ENABLE_DNN=0`,
`GGML_SYCL_ENABLE_GRAPH=0`, and `GGML_SYCL_PRIORITIZE_DMMV=0` rather than
depending on source defaults.
Each selector-on process must report both `flat` and `recurrent` first-hit markers using
`path=reordered_single_col_mmvq`, a ready reordered weight, and two calls per
dispatch. The marker must also identify the exact named `[6144,5120,1,1]`
weight and the exact flat/recurrent input and output dimensions. Its final
counters must be exactly:

```text
flat_dispatches=1
recurrent_dispatches=1
flat_multicol_suppressed=1
recurrent_dmmv_suppressed=1
reorder_ready_dispatches=2
single_col_mmvq_calls=4
violations=0
```

The selector-off oracle must emit no canonical first-hit, summary, or violation
markers. Its startup echo, if visible, must be zero.

Any violation marker, missing marker, duplicate summary, unexpected counter,
wrong candidate shared-object mapping, changed source identity, nonregular
artifact, or byte difference fails closed. Common-logger timestamp/level
prefixes are accepted. The startup selector echo is checked if visible; the
sanitized launcher identity remains authoritative if verbosity suppresses it.

Execute mode also follows the lane's operational safety boundary:

- acquire the standard selected-card lease, or validate an inherited
  `QWEN36_GPU_LEASE_FD` against that exact lease path;
- make one bounded preflight XPU-SMI sample and require at most 256 MiB used;
- put each worker in a private process group, guarantee bounded group cleanup
  on timeout or termination signal, and fail if forced cleanup, a nonzero exit,
  or any survivor is observed;
- run a passive kernel-journal and worker-log checkpoint after each of the first
  two workers before launching the next worker;
- retain and scan the full passive kernel-journal window plus all worker logs
  before any postflight probe;
- skip postflight as probe-unsafe after any timeout, cleanup, survivor, worker
  fault, kernel fault, or journal failure; otherwise make one bounded
  postflight XPU-SMI sample, with no retry loop, and require VRAM to return to
  the preflight envelope.

## Use

First perform the CPU-only build/dependency check. Use a fresh evidence path;
the launcher refuses to reuse either the evidence directory or component build
directory. Use a different fresh component-build path for every later run too.

```bash
python3 run-q8-canonical-mmvq-component-gate.py \
  --source-dir /absolute/path/to/candidate-llama.cpp \
  --ggml-library-dir /absolute/path/to/candidate-llama.cpp/build-sycl/bin \
  --component-build-dir /dev/shm/q8-canonical-component-build \
  --output-dir /absolute/path/to/new-build-only-evidence \
  --build-only
```

That build-only form is explicitly recorded as an unsealed offline
compile/dependency smoke test when it uses the all-candidate build. It is not
authoritative evidence for the hybrid model study. A build-only check can also
take `--runtime-manifest` and will then be labeled sealed.

After candidate review and passive GPU preflight, execute on one explicitly
selected B70 with the exact study hybrid:

```bash
python3 run-q8-canonical-mmvq-component-gate.py \
  --source-dir /absolute/path/to/candidate-llama.cpp \
  --ggml-library-dir \
    /mnt/fast-ai/runtime/llama.cpp-15586e2d-q8-c2-canonical-109eee6f-hybrid \
  --runtime-manifest \
    /home/steve/llm-optimizations/experiments/qwen36-27b-q8-gguf-b70/runtime-manifest-canonical-q8-c2.json \
  --component-build-dir /dev/shm/q8-canonical-component-build \
  --output-dir /absolute/path/to/new-component-evidence \
  --gpu-index 0 \
  --execute
```

The standalone executable links directly to the selected directory's `libggml`
and `libggml-base`; the launcher additionally requires `libggml`,
`libggml-base`, `libggml-cpu`, and `libggml-sycl` to resolve to that exact
directory and records their resolved paths, sizes, and SHA-256 hashes. The
authoritative command above therefore proves the candidate `libggml-sycl` in
the same baseline-companion hybrid used by the model study.
Execute mode requires the manifest and verifies its origin-first loader policy,
schema, exact selector contract, clean candidate source HEAD and SYCL source
hash, and resolved filenames, sizes, and hashes for all four GGML objects before
any GPU probe. It also rechecks the manifest and runtime objects after the gate.

Offline parser and artifact tests:

```bash
python3 test_q8_canonical_mmvq_component_gate.py -v
```

## Interpretation boundary

A pass proves only that this isolated Q8_0 MUL_MAT shape follows the intended
two-single-column route and is bitwise invariant against a selector-off c1
component oracle for the two supplied vectors and bootstrap orders. It does not
cover upstream recurrent state, KV/cache
state, scheduler batching, sampling, other model weight shapes, natural EOS,
or performance.

The component gate can reject a bad candidate early, but it cannot promote one.
A candidate-runtime-matched sealed model-level c1 oracle, the two-wave model-level
baseline/candidate crossover, synchronized natural-stop testing, and the normal
performance/quality gates remain mandatory.
