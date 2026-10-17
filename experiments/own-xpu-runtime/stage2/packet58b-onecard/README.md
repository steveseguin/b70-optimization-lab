# Packet 58b: repair the one-card copy-queue import

This is a separate source copy of sealed packet 58. Only the native copy
queue handle changes: an asynchronous **in-order immediate command list**
on the same copy-only engine replaces a regular command queue. Explicit
ownership and cleanup use `zeCommandListDestroy`. No arithmetic, expert
layout, allocation size, cache policy or kernel changes.

The original K1a failed during `Runner` construction, before its case log
opened. The failing import is `sycl::make_queue` for `native_copy_`:
Intel UR Level Zero v2 rejects a regular queue handle with error 44.
[Root-cause evidence](evidence/root-cause.json) pins Intel's adapter source,
the installed adapter hash and its matching diagnostic string. The saved
[failed native log](evidence/failed-K1a-native.log) and
[window receipt](evidence/failed-K1a-window.json) preserve the incident.
This is source-based localization, not a GPU trace or a successful rerun.

The 48.6 GB full-model pin was never attempted by K1. Neither large-allocation
limits nor host-USM kernel access explains this constructor failure. Their
real-device qualification remains pending. Zero-copy remains the preferred
path when both K1 runs pass their existing exactness and bandwidth gates;
otherwise the existing streamed path is selected. Unsupported host USM still
fails closed: this repair does not turn unsupported hardware into a pass.

[CPU build and lean gates](CPU-BUILD.md), [coordinator command](WINDOW.md),
[closeout](CPU-PREPARATION-CLOSEOUT.md), and
[task note](../../../../notes/2026-10-17-own-runtime-packet58.md).
The same one-card model, BF16 KV, oracle, memory admission, safety checks,
K1-first stage order and fail-without-retry rules apply.
Other copied design/review documents describe the parent packet; their old
CPU counts are historical, not fresh 58b sanitizer results.

Credit Intel's SYCL/Unified Runtime interop contract for the queue-handle fix.
Credit Niko1221 / Strata for the inherited hot-expert cache idea. The runtime
remains independently written lab code; no external implementation was copied.

Both builds and the lean CPU gates pass, including the unchanged parent K1
output hash. The retained build is 148.3 MB. `build-receipt.json` binds the
final source, binaries and gates. Device windows remain pending.
