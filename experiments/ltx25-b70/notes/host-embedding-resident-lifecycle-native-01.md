# Actual CPU encoder replacement lifecycle qualification

On September14 after the user-confirmed reboot, bounded GPU health assessment,
and separate root recovery admission, the prepared guarded CPU fixture ran once.
Child8812 exited0. All six cases passed in1.590seconds of test-body time; that is
not a video speed measurement. XPU and CUDA remained uninitialized, all guards
were intact, and there were no skipped tests. Locked parent pre/postflight
found unowned render nodes and no detected current-boot kernel fault.

The driver and fixture match the [prepared and independently reviewed sources](host-embedding-resident-lifecycle-cpu-prep-01.md).
The native result SHA is
`c9c2d81db33ab5d3174aaaaa87a31c6cf03e5d7923f1b9c305bae554e51ea452`.
The exported [evidence manifest](../data/host-embedding-resident-lifecycle-native-01/manifest.json)
binds original result, startup identity, test log, per-case receipts, parent
pre/postflight and the successful new check-only admission. Larger files are
losslessly compressed, with both stored and original hashes recorded.

Actual tiny CLIP and ModelPatcher ownership passed control→host-table→control:
output bytes/dtype/shape/stride matched, old encoder/host owner weakrefs died,
and native loaded-model registry entries disappeared before replacement.
Unchanged fake nonencoder owners stayed identical across the three generations.
Each retained actual clone, model or component tuple correctly stopped
replacement and latched further transitions. Low restore budget stopped before
retirement; low constructor budget stopped after proven old-owner release and
before replacement allocation. Per-case evidence SHA is
`4ca154fd9b77a4389e853a4e80eb4c543aead688a4dc51ed7e123aaaace95b9f`.

This is actual CPU lifecycle and tiny output qualification. Nonencoder objects,
available RAM and full-checkpoint geometry are fakes in the fixture; it does not
qualify large-model allocation peaks, XPU release/residency, complete video/audio
outputs, speed or endurance. The original packet11 remains frozen and failed.
Next: build a new runtime with the qualified resident source, bind updated
client receipt validation, review cold-assembly RAM admission, then qualify
full clips on one persistent application. Keep original BF16,256²,25frames,
24fps,8+3steps and all four raw oracles unchanged.
