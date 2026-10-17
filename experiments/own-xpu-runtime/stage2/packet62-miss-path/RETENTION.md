# Build and evidence retention

The build is local research evidence, not a publicly reproducible model recipe.
Source, selection seals, build receipts, exact compile/link commands, raw CPU
byte pairs and compact state/diagnosis receipts are tracked. Compiled binaries,
objects, generated mirrors and verbose per-case state dumps stay under ignored
`build/`; each selection's binary is a hardlink to the same build/device file.
No parent source or object is modified.

`build_engine.py` verifies packet61's build-source map and reuses its unchanged
objects by hardlink, with path-derived unique filenames. It compiles main,
the selection parser, and the focused host copy fixture. It uses the same
compiler flags and precise-math settings as the parent. Retain packet61's
objects and `build/fusion-rope.hpp`; parent build instructions and receipts
explain their reconstruction. A fresh unsealed packet build first needs:

```bash
P=experiments/own-xpu-runtime/stage2/packet62-miss-path
mkdir -p "$P/build/tmp"
ln "$P/../packet61-spin-hcfusion/build/fusion-rope.hpp" "$P/build/fusion-rope.hpp"
```

Then follow README's CPU commands. Do not run this bootstrap over an existing
header or rebuild a sealed selection. The generated header bytes and both
original and mirrored source paths are bound in the build receipt. The host
fixture is linked with the inherited host objects and never with device
libraries.

Preliminary CPU outputs remain under `build/preliminary-cpu/` and
`evidence/preliminary/`. They tested a host memcpy copy oracle; final gates use
the same tile routine as the device kernel. `build/attempt2-cpu/` and
`evidence/attempt2/` retain the earlier reset-harness attempt. Its final
receipt lookup incorrectly followed the reset output directory, although the
rank writes teardown receipts to its original launch directory; the harness
was fixed. The standalone copy fixture also corrected its runtime-overhead
allocation lifetime to `process`. These were CPU test-harness errors, not GPU
incidents. No device was opened or reset.

The raw equality pair is about 0.41 MB per file. Aggregated CPU-gates JSON is
retained because it binds every selection, negative control, state hash and
metadata check without retaining huge scratch dumps in Git. Any file flagged
by repository size checks is evidence, not disposable generated cache. The
packet manifest records logical build usage (including repeated hardlink
views) and unique-inode usage; both remain within the owner's 400 MB bound.

Large tracked artifacts are intentional:

| Artifact | Bytes | Why retained / restoration |
| --- | ---: | --- |
| `rope.bf16` | 4,194,304 | Unchanged immutable runtime input; restore byte-for-byte from packet61's same file and verify the build receipt SHA256. Git shares the existing identical blob. |
| `evidence/cpu-gates.json` | 3,881,057 | Final per-selection target/state/negative-control receipts; regenerate only in a fresh unsealed reconstruction using the recorded host build and CPU gate. Its SHA256 is bound by every selection seal. |
| `evidence/preliminary/cpu-gates.json` | 2,779,126 | Earlier host-memcpy control evidence, explicitly preliminary; its original build/binary receipts and local host/device binaries remain alongside the preliminary run retention paths. Never present it as the final tile-routine gate. |
