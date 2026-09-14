# First encoder GPU screen: strict startup ordering defect

The first native control clip completed on PID75850. All four output archives
were independently rehashed and matched the original baseline bytes exactly.
The unchanged comparator correctly rejected it because capture reported
`deterministic_enabled=true, deterministic_warn_only=true`. This is a failed
qualification, not a speed result. The client halted before any candidate or
second request. The failed capture and preview remain protected externally.

Evidence: [failed campaign](../data/encoder-screen-01/progress.json),
[comparison error](../data/encoder-screen-01/encoder-screen-01-r01-control-boat-compare.log),
[capture](../data/encoder-screen-01/capture-summary.json),
[independent diagnostic](../data/encoder-screen-01-strict-failure-diagnostic.json),
[profile](../data/encoder-screen-01/profile.json), and
[runtime log](../data/encoder-screen-01/server.log).
First-use preview latency was125.50s, including loading; it is not warm speed.
The initial actual encoder placement confirms 287/289 norms and all48 layer
scalars are still on CPU under control. This supports testing small-state
residency but establishes no benefit yet.

## Cause and correction

The new launcher set strict determinism before `runpy` loaded ComfyUI.
`comfy.model_management` then set warning-only mode during import. The original
working `serve-speed.py` imported this module before its final strict setting;
the prepared encoder launcher missed that ordering. Earlier CPU unit and
read-only startup checks did not execute this import path, so they failed to
catch the integration defect. The output checker was not weakened or bypassed.

The [launcher patch](../patches/encoder-startup-strict-after-import.patch)
restores the known original order: parse arguments, import model management,
enable strict mode, verify it, then execute main. It also records the flags
after import, bound to the application identity. The port availability probe
uses SO_REUSEADDR so an old TIME-WAIT socket does not masquerade as a live
listener; it does not change kernel settings.

`prepared-encoder-03` differs from the frozen packet02 in exactly one inventoried
file: `launch/serve-encoder.py`. Model code, weights, graph templates, encoder
patches, diagnostics, identity checker and all comparison helpers are unchanged.
Its [manifest](../data/encoder-runtime-prepared-03-manifest.json) has SHA256
`d391ac4236e7ea683af1e1cdae5a4f020e608e20c4ff849d9fe958b524d028e7`.
The copied launcher's read-only check passes. The active old packet is untouched.

The [new screen preregistration](../data/encoder-screen-02-prereg.json) retains
the original25-request schedule and gates. Its
[thin wrapper](../scripts/run-encoder-screen-02.py) verifies the frozen client,
checks the strict-startup receipt, and changes only campaign/output names before
calling the original client. This preserves the failed campaign rather than
resuming or overwriting it. Deployment and results follow after the import-order
regression test; no performance improvement is claimed by this source fix.

The [actual-import regression](encoder-startup-determinism-regression.md) passed
all11 checks: frozen02 reproduces the warning-only reset; fixed startup restores
strict mode and its identity-bound receipt. Both paths were CPU-only. Original
PID75850 then exited cleanly after one controlled SIGINT for this verified source
correction. Corrected PID78769 is ready with strict mode verified after import;
encoder-screen-02 is active. No device fault or automatic retry occurred.
