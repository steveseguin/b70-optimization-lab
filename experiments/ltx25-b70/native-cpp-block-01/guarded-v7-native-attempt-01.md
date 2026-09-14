# Guarded v7 native attempt — cache-system query safely refused

Parent ran one bounded diagnostic (execution session 74927, Python PID 112422),
which exited 1. The v7 virtual registry installed with the exact six native
unindexed entries and the original dictionary identity. One eager CPU case
completed. During the first Python-boundary compile, AOT cache-key construction
reached a different discovery path:

`AOTAutogradCacheDetails` → `FxGraphHashDetails` → `CacheBase.get_system` →
`torch.cuda.current_device`, trapped at `codecache.py:340`.

The actual stack is preserved in `guarded-v7-result-01.json`; there is no need
to infer this path from sampling or a later failure. No compiled block result,
C++ arm call or cache-save metadata omission was recorded. Both
`xpu_initialized_at_exit` and `cuda_initialized_at_exit` are False, and the result
reports no fault latch at exit. Parent owns separate postflight/host evaluation.

The policy finalizer fields are False because each starts by checking the
already-sticky accelerator guard. Their errors report the existing halt; these
fields are **not backend-initialization indicators** and do not establish a
separate registry/config/metadata corruption. The separate actual initialization
fields remain False. The global halt was neither cleared nor retried.

Copied the exact pre-Torch startup receipt into `guarded-v7-startup-01.json`.
SHA256: `de534a9245b5444e8d63286c9bd6037fd1f5ee15377296403ef18d3af47a0b53`.
Its original location is
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/native-cpp-block-cpu-guarded-v7-01/startup-identity.json`.
The copy's bytes, source path and receipt hash were verified without native
imports or device/process operations.

Source/evidence hashes and excerpts are preserved in
[guarded-v7-cache-system-source-01.json](guarded-v7-cache-system-source-01.json).
The next source-only comparison is in
[CPU-CACHE-SYSTEM-PROPOSAL-01.md](CPU-CACHE-SYSTEM-PROPOSAL-01.md).
All v7 harness/helper sources and prior evidence remain unchanged.

Root postflight at17:54:37 UTC passed: probe absent, unchanged LTX PID84255,
empty queue, identical full endpoint identity, only that PID on all four render
nodes, no fault latch or new kernel entries. See
[postflight](guarded-v7-postflight-01.json). No application or host action.
