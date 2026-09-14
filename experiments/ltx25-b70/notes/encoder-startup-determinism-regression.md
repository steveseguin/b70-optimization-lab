# Actual startup import-order regression

The [CPU regression driver](../scripts/test-encoder-startup-determinism.py)
executes the real launcher's AST tail after device preflight, replacing only
`runpy.main` with a marker. In fresh subprocesses it imports the actual pinned
`comfy.model_management`, with real `--cpu --deterministic` argument parsing.
Discovery functions are stubbed because upstream queries XPU counts even with
`--cpu`; XPU/CUDA initialization attempts must remain zero. No server, watcher,
model tensors, GPU computation, process control or loaded-source edits occur.

The [receipt](../data/encoder-startup-determinism-cpu-01.json) passed all 11
checks. The frozen `prepared-encoder-02` launcher reproduces the actual failure:
its earlier strict setting is replaced by `warn_only=True` during Comfy's first
model-management import. The fixed launcher executes the sequence strict →
warn-only import → strict restoration. Flags remain strict at the main-entry
marker and after main's now-cached model-management import.

The test also validates that `determinism-after-import.json` records strict
flags, the correct stage and the hash of the server identity written by the
same startup tail. This is identity-binding evidence, not a watcher or complete
server test. The unchanged capture gate remains required for real clips.

The driver and both launcher sources are hash-bound in the receipt;
[full output](../data/encoder-startup-determinism-cpu-01.log) is preserved.
During fixture setup, plain mocks conflicted with Dynamo's `__wrapped__`
introspection, so discovery wrappers now preserve function metadata. The fixture
also creates the user/input/temp directories that the omitted real preflight
normally creates. Those were test-fixture corrections; no runtime patch or GPU
retry occurred in this regression task.
