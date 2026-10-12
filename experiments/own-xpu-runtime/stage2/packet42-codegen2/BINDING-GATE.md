# Native admission repair and CPU gate, October 12

The failed K0 did not reach a kernel. Floor and tiny shared `CompileSmoke`,
which called `Device::compute(op, {}, {})` before building a kernel bundle and
submitting a barrier. The real owner rejects empty bindings. The protocol mock
never exercised that code. Both programs now call the existing bundle-only
`p42_compile_smoke` helper before constructing `Runner`, matching the other
four programs and packet29 jit-smoke. No shared owner file changed.

The audit found no other empty compute list in the six native programs or
their invoked incumbent/candidate submission paths. Floor binds input, output
and the parameter allocation even for by-value kernels and zero-length split
segments. GEMV binds weights, inputs, outputs and its applicable route/status
and scratch buffers; non-GEMV calls bind their actual fixture/control/scratch
allocations. No dummy owner exception or unbound warm-up remains.

## Real owner admission gate

Run from the repository root:

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B \
  experiments/own-xpu-runtime/stage2/packet42-codegen2/binding_gate.py
```

This compiles **the six native main functions and the native submission
implementations**, including the same device-side-choice branch of the host
validators. `OWN_RT_HOST_ONLY` is deliberately not defined. The actual
packet29 `owner.cpp` and `owner_retire.cpp` are compiled without changes. The
host Backend is extracted from packet29's real GEMV fixture gate in its
validation-only mode; a trace replaces its already-disabled arithmetic call.
This is not `mock_native.py`, nor a rewritten argument builder.

The only gate-specific switches skip kernel execution, result comparisons,
and the device bundle API. Every allocation, binding builder and native
admission validator is retained. The native GEMV generator keeps all 216
iterations in both builds, so the gate reaches all eight warm-ups, 200 timed
iterations, eight postflights, and every rotated bank. CPU trace durations are
zero and are not measurements or output-parity evidence.

| Program/window | Coverage | Compute submissions |
| --- | --- | ---: |
| All six / K0 | Six actual argument parsers and compile-smoke call boundaries; no compute | 0 |
| Floor / T1 | 1,176 matrix rows + four burst rows, all 200 repetitions | 1,355,544 |
| GEMV / K2 | Four shapes, five shape/candidate pairs, both arms, reread/rotation modes; complete 216-iteration loops | 4,752 |
| Parallel / K2 | Route-gather and GDN, incumbent/candidate, 200 repetitions | 2,200 |
| Production route / K2 | Both paths, 200 repetitions | 1,800 |
| Tiny / K2 | 129 rows, 333 byte-scenario paths, 26 timed rows | 11,011 |
| Extras / K2 | 70 rows, 23 timed rows, including scheduled/in-place controls | 11,366 |

Nine negative controls require rejection of empty compute, pinned compute,
released compute, oversized copy, aliased copy, undersized binding, misaligned
binding, scratch alias and conflicting writable alias. A real bound compute
is the positive control. These exercise the real owner and native validators.
**No check is mirrored:** extent/alignment/alias checks remain compiled from
the exact native submission source, including device-build-only host code.

The compiler's `-fsycl-host-only` still emitted offload bundles on this install;
the inspection rejected that build before execution. The final host gate uses
plain C++ (`-fno-sycl`) and checks ELF symbols/sections before any execution:
no offload images, SYCL image registration, platform enumeration or `zeInit`.
It links SYCL type support but never calls discovery, bundle creation, queues,
or `SyclOperation::submit`. No device binary was run by this repair.

The [gate receipt](binding-gates.json) retains commands, host binary hashes,
all operation types with call/binding counts, negative controls, and hashes
of the compiled source/header dependencies. `seal.py` refuses missing,
incomplete or stale gate evidence and includes its hash in the build seal.

This gate establishes argument/binding admission, not SYCL bundle compilation,
kernel arithmetic or speed. The new coordinator K0b/T1b/K2b windows must still
establish those. The arithmetic CPU gates for tiny and extras were rerun under
both host compilers twice; all 16 wrapper tests pass, including failed K0
blocking both dependent windows without a fault latch.

Failed-window evidence and original hashes are retained under
[evidence/20261012-k0-empty-bindings](evidence/20261012-k0-empty-bindings/README.md).
Historical assembly reports retain their original binary identity; the repair
module proof checks their SPIR-V bytes in the rebuilt executables.
