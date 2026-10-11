# Packet 24 port: immutable parameters and bounded queue copies

Packet 24 was not read, edited, built or run in this task. Apply these deltas to
its corresponding files, then run its own gates. This is a storage/submission
change; keep its kernel improvements and arithmetic intact.

1. `owner.hpp` / `owner.cpp`: port `SubmissionCounts`, `submission_counts`,
   `preparing_parameters`, `freeze_parameters`, `copy_is_device_to_device`,
   `Device::compute`, `Device::wait`, `CopyEngine::copy`, and `parameters`.
   Parameter keys include card identity. Frozen tables reject a new or changed
   byte sequence **before** allocation/copy. Every lookup compares the CPU
   parameter bytes with those uploaded during preparation. Scope counts to a
   token by subtracting snapshots. D2D byte kernels count as launches and
   `byte_move_launches`; H2D/D2H queue commands count as `device_copies`.
2. `kernel_guard.hpp`: port `packet23::submit` (rename namespace if desired).
   During preparation it returns an empty event without submitting the handler.
   `packet23::parameters` still calls the owner cache. Keep `checked` and its
   1,024-byte static assertion. `kernel_gate.py::mirror` replaces each kernel
   implementation's `q.submit` with the preparation-aware wrapper. Backend
   copy/marker submissions must remain real submissions during preparation.
3. `backend.hpp::Context::compute` and the one-card `sycl_device.cpp` overlay
   in `kernel_overlay.py::apply`: preparation calls the operation's same submit
   method to construct and upload its parameter blocks, but creates no compute
   event. Normal execution keeps event-ID assignment after submit. In
   `Context::copy` and the one-card copy overlay, D2D moves use byte kernels;
   only host/device transfers call `h.memcpy`. Keep peer pre-drains and queue
   dependency isolation. The unused packet7 Stream copy arm is covered too.
4. `runtime_kernels.hpp::Spec`, `adapter.cpp::Bound` / `ChainItem`: preserve
   the naturally aligned parameter layout and explicit seven-byte zero padding
   in `Spec`. Keep the `sizeof` assertions (Spec 440, Bound 696, ChainItem 496). `CMakeLists.txt` uses
   `-ftrivial-auto-var-init=zero` to make remaining local aggregate padding
   deterministic. Port the layout to producer and consumer together. Never pack a std::array
   of pointers; the fail-fast UBSan gate rejects that alignment error.
   `gemv_batch.cpp::gemv_batch` and `adapter.cpp::submit_chain` construct the
   parameter table in CPU builds too, so mock gates observe table copies.
5. `main.cpp::Engine` and the preparation block after `initialize()`:
   traverse the same resident dispatch with `preparing_parameters=true`, drain,
   then freeze. Do not write preparation events to per-site timing output. In the native
   `Engine::finish` path, preparation must return before adding profiling events:
   a prepared operation has no compute event, including under W2d launch timing.
   Arithmetic kernels do not run in this pass. Positions, active flags, routes,
   token history and admitted attention slots stay in existing device buffers.
   No resident kernel's metadata depends on a per-token host scalar.
6. `Engine::initialize`, `put`, `prepare_token`, and the token `step` lambda:
   allocate fixed token/result packet buffers; concatenate token ID and decoded
   lookup rows into one upload per card. Scatter with ordered byte kernels.
   Snapshot copies and peer handoffs are ordered byte kernels too. Gather error,
   result and optional layer captures into one readback per card. These byte
   kernels change transport only, not BF16 stores or reduction order.
7. Token rows report `device_copies`, `device_copies_by_card`, `host_waits`,
   `launches`, and `byte_move_launches`, retaining `kernel_submissions` for the
   arithmetic-only count. `host_waits` counts explicit owner event waits;
   completed-queue retirement synchronizes are not included. The resident
   unchecked path refuses more than two queue copy commands per card/token.
   Checked localization and the CPU one-card weight-streaming oracle are
   diagnostics with additional transfers, not this resident speed budget.
8. `copy_budget_test.py` exercises actual mini arithmetic and real plan metadata
   with a CPU-only sparse counting backend (`--count-submissions` is unavailable
   in native builds). It also bans copy/fill/shared-USM calls outside the two
   audited native backends. `failure_test.cpp`'s `immutable` mode proves 876
   cached submissions add zero copies/waits and changed bytes are refused.
   `depcheck_build.py` and `instrument21.hpp` skip arithmetic during preparation
   and track parameter staging writes for the randomized dependency checker.
9. `window.py::NativeChild`, `native_exec.py`, and `test_window.py`:
   `--native-nice` uses a transient user service; W2/W3 default to 0 while their
   wrappers stay at 19. Keep closed native environment, graceful main-process
   signals, actual-priority receipt, no restart, and existing deadline gates.

CPU gates do not measure the adapter's submission latency. Run fresh K0, both
K1 owners, W0, W2 and W3 with packet 24's own binary hashes and fresh output
names before reporting any new speed. Never reuse packet 23's K0 receipt.
