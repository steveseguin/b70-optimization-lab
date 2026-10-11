# Independent sanitizer review

Review scope: `depcheck.hpp`, `instrument.hpp`, `build.py`, the original packet16 owner/backend/adapter/performance sources, packet15 kernel indexing, and packet4 interpreter semantics. The reviewer received the code and requested invariants rather than a proposed fault conclusion. No device code ran.

## Findings fixed

1. **Event retirement erased unfenced hazards.** Initial `Checker::clear` allowed completed work whose completion had not been made visible by a host wait. Clearing its writer/reader history silently admitted a following unconnected read. It now requires `done && visible`. The test explicitly calls the scheduler without a host fence before retirement.
2. **Partial overlap escaped allocation registration.** Initial `Checker::add` only checked the same base address. It now rejects any live intersecting allocation interval; stale dead intervals may be removed on allocator reuse. The tests also require that reused storage starts poisoned.
3. **Diagnostics were insufficient to prevent CPU use-after-free.** Initially, a pending release could record an error and continue to `operator delete`, after which allocator reuse could make a stale closure appear live. Pending release now retains ownership and throws. Double release and host writes after release also fail before a caller can free or write storage. A poisoned index or dead allocation blocks execution of its closure. Execution errors use the submitted work's site name.
4. **Unused bindings bypassed ownership validation.** The device backend checks all passed pointers; access metadata may intentionally omit unused aliases. `Backend::compute` now validates every binding independently of its access list, including omitted/unused slots.
5. **Whole-state append writes hid untouched bytes.** `describe_ng(pool)` and the tiny `qsa_append_pool` contract now write only the current BF16 KV/raw positions and newly completed pooled block. Pooling reads prior raw elements only when completing that block. `select` reads only the produced pooled prefix. The scalar interpreter remains explicitly different: it copies full outputs into and out of its scratch arena, so its output accesses really span the whole output.
6. **Copying poison incorrectly initialized the destination.** A general submission write initializes its declared output, but `memcpy` must preserve the source's byte poison. `Checker::copy_bytes` now copies the initialization intervals independently from dependency history. Tests cover initialized prefixes, poisoned suffixes, and a second transfer preserving poison. Copies still own distinct writer events and obey RAW/WAR/WAW rules.
7. **Patched code/header identity needed one include path.** The original instrumentation included packet15's original header while the patched adapter could include a second patched file with the same definitions. The parent changed build staging to give both one selected header path. The review also requested compiler dependency files to receipt the transitive source/header closure, not only explicitly staged files.

## Verified checker properties

`review-checker-tests.log`: **33/33 passed**, CPU only. The tests independently exercise missing RAW and WAW edges; both outstanding readers of a WAR; a transitive diamond; cross-queue order and missing cross-queue edges; same-queue submission order granting no implicit dependency; executed work versus fenced work; a host fence not exposing unrelated work; wrong device/context; disjoint and overlapping byte ranges; offset copies; poisoned indices; pinned host slab reuse; lifetime and allocation reuse; alias read/write in one operation; and ancestry spanning more than two 64-bit words.

The randomized executor test creates two independent ready operations, asserts `max_ready == 2`, and finds a result mismatch for at least one of 32 seeds when the edge is missing. Adding the edge yields identical results in synchronous mode and all 32 random seeds. A real plan whose owner appends the previous event to every submission naturally has `max_ready == 1`; multiple seeds do not manufacture concurrency absent from that declared DAG.

Tests build with:

```sh
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 g++ -std=c++20 -O2 experiments/own-xpu-runtime/stage2/packet19-depcheck/tests.cpp -o experiments/own-xpu-runtime/stage2/packet19-depcheck/build/checker-tests
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 experiments/own-xpu-runtime/stage2/packet19-depcheck/build/checker-tests
```

## Limits that must remain explicit

- This is a submission-DAG and declared-range sanitizer, not machine-code address instrumentation. Incorrect arithmetic *inside* an otherwise correctly described kernel can evade it. Device-side range checks remain necessary.
- Kernel metadata describes the valid-input path. Some kernels return early on a sticky error, invalid router value, or inactive request; those conditional paths do not necessarily write every declared output. Host gates on normal inputs do not prove poison tracking of every failure-path internal store. Copy poison, never-written index input, and explicit lifetime errors are tracked independently.
- Full input reads may conservatively include unused state elements. Exact byte writes are especially important: overstating a write would remove poison or earlier readers. Current pool append writes are precise; some scalar-interpreter and matrix contracts remain deliberately whole-allocation based on their full loops.
- Host-operation scheduling is not every native kernel launch: native split GEMV partial/reduction kernels and internal barriers need separate source enumeration. An operation closure running atomically on CPU cannot reveal an internal native event edge defect.
- Shared-context pointer identity does not prove that the driver mapped the allocation into both devices' page tables. The checker cannot determine `EnableDeferBacking` effects or establish the fault's native cause. A clean CPU gate is not permission to bypass FAULT HALT.
- `--source` support for packet18 must fail if adapter operation types or access contracts change without an update. Text rewrite anchors and the selected compiler dependency manifest must be reviewed against the exact packet18 source identity.

## Follow-up: CPU fatal-owner retention

An additional runtime failure was confirmed from source: poisoned-index rejection in `Checker::execute_until` reaches packet16 `main.cpp`'s exception handler, which calls `Engine::shutdown`; a second failing wait produces an unsafe owner receipt, and `Engine::shutdown` invokes `hold_for_supervisor` indefinitely. This was the native owner's intended device-retention behavior, accidentally inherited by the CPU sanitizer. An exception catch around the generated top-level main cannot reach past that wait.

`build.py::cpu_owner_overlay` now stages the actual selected packet's `owner.cpp` and replaces **only the body of `ownrt::hold_for_supervisor`** with `depcheck::fatal_cpu_exit()`. The helper in `fatal_cpu.hpp` records the existing violation list, executed count, canceled pending count and event/site list, flushes output, and exits the CPU process with status 2. It does not run, mark completed, or free any pending submission through the owner. The operating system reclaims this CPU-only process's memory. The original native owner and every device source remain untouched.

Valid-path impact: the owner functions governing allocation, compute, copy, event chaining, waits, retirement and ordinary shutdown are unchanged. The generated owner acquires a CPU report helper include, and the noreturn supervisor body changes solely when shutdown has already been refused. This changes build identities but does not change any valid arithmetic, submission, or completed teardown path.

`test-fatal-owner.py` builds the real packet16 owner with that same overlay and the actual sanitizer backend in a separate temporary subdirectory of packet19's ignored `build/`. It never rebuilds `build/patched`, `build/shipped`, or packet18. Both tests have a five-second subprocess deadline:

- A never-written device index fails in the actual owner `wait` path, records `uninitialized INDEX`, cancels one pending submission, executes zero closures, and exits 2.
- An intentionally untracked producer simulates a missing owner edge. Strict checker mode reports RAW in the real owner `compute` path; its stored backend fault forces refused shutdown. It cancels one pending producer, executes zero closures, and exits 2.

Both operation closures abort if called, so a successful exit-2 test also proves that cancellation did not execute the unsafe work. `fatal-owner-test-results.json` retains both reports. The temporary source/object/binary directory is deleted automatically after the test.

```sh
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet19-depcheck/test-fatal-owner.py
```

The packet18 follow-up review confirmed its 19 bindings: sticky error at 15, rope table at 16, position at 17, active at 18, and the tiny adapter's rope table at `tail()+4`. Source selection stages packet18's own `runtime_kernels`, performance and kernel headers. The native enumeration remains specifically packet16's frozen dense unrouted split4 dispatch; routed split reductions would additionally read routes and partials would write status, so that expansion must not be generalized without corresponding contracts.

## Final valid-path regression after the fatal-owner fix

A separate `build/final-patched/depcheck-runtime` build completed without replacing the original shipped, patched, or packet18 binaries. Its SHA-256 is `316bbf6d10e784921abb18027a99cbc1963feab9e6fbc7ebd4a619c345f5014b`. `final-integration-gates.json` binds the binary and complete build manifest to **104/104 passing case runs**: the original 13 integration cases, both `parallel` and `core`, and seeds 0, 1, 17, 73. This repeated only mini arithmetic and real-plan metadata validation; no additional real-model inference was run. All eight new integration scratch directories were removed after successful receipt collection. The original `integration-gates.json` hash was checked unchanged.

`final-source-equivalence.json` records raw hashes and exact relocation-normalized hashes. Raw generated files differ because their absolute `#include` roots contain `build/patched` versus `build/final-patched`. Replacing **only that containing directory string** with `<BUILD>` makes all five requested translation-unit/instrumentation files byte-identical, and all **36 common generated C++ sources/headers** are likewise byte-identical. The sole added generated source is `owner.cpp`, with the previously reviewed retained-owner function replacement. This establishes valid-path source identity without claiming unequal raw bytes have equal hashes.

Run the final integration receipt generator with the Python environment that supplies NumPy and jsonschema:

```sh
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 /home/steve/.venvs/vllm-xpu/bin/python -B experiments/own-xpu-runtime/stage2/packet19-depcheck/run_final_integration.py
```

Failure-report limitation: the existing `executed` counter counts closures that completed successfully. A closure that itself throws after partial CPU work remains unfinished and is included in canceled work. The helper never invokes any pending closure; the two fatal-path regressions specifically establish zero closure invocations for the tested poisoned-index and missing-edge failures. It does not promise to roll back arbitrary partial CPU writes, and is never used with a device backend.
