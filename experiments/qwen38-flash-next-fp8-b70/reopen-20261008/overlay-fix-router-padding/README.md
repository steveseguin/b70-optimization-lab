# Screen 1b router-padding compatibility fix

Applied to the repository production overlay on **2026-10-11**, CPU tested,
not natively qualified. The diagnostic uses the exact same two router files.
[Root cause, receipt hashes and identity argument](../../../../notes/2026-10-11-moe-boundary-caught-router-ids.md).

V2 marks the 64-token profile batch as padding. Native top-k emits signed
`-1` IDs for those rows; the pinned 0.1.14.1 aligner lacks negative-ID guards.
For `B70_SCREEN1B=1` on XPU, both ordinary and bias router mask helpers return
`None`, selecting ordinary routing for every row. This covers profile, MTP
and graph padding without changing the shared InputBatch or other platforms.
It deliberately trades padding-skipping work for compatibility with the pinned
wheel. No weights, valid routing arithmetic or expert maps change.

The historical lab native fix is
[0004 / commit 2f829747](../../../../patches/qwen38-flash-next-fp8-b70/vllm-xpu-kernels/0004-fix-moe-ignore-padding-sentinels-during-alignment.patch).
That patch remains an accepted older-runtime mechanism; it is absent from this
wheel, not superseded by it. A future native port needs its own build and gates.
This scoped Python fix does not claim to repair the wheel for arbitrary callers.

`router-padding.patch` is relative to `reopen-20261008/`. Its frozen repository
preimage is `3a6435133de4f2fc5b937e5b48033832d622df3d`. `base-runtime/` preserves
both pristine router files from official vLLM
`ced6857afa0ea7b2e3f0846a62e1394e90f15607`, which also match the source checkout.
The patch manifest pins preimages, outputs and runtime originals. The runtime
installer refuses mismatched original bytes before replacing any file.

To reseal after an authorized source edit, copy the two production router files
into this directory's `copies/overlay/`, run `python3 -B build_patch.py`, copy
`copies/overlay-manifest.json` to the lane's `overlay-manifest.json`, then run
`python3 -B build_patch.py --check`. Copy those same two router files into the
boundary package and run its builder and restricted CPU suite. The boundary
builder carries the same native preimage pins and production semantics.

[Two exact stage/run commands](../overlay-moe-boundary/README.md#future-authorized-window-command--not-run-by-this-task)
prepare and run the fixed production path with the strict boundary ON. Use
fresh destinations and coordinator-supplied admission. No runtime, server,
GPU, systemd operation or model request ran during this task.

[CPU receipt](../evidence/moe-boundary-router-ids-20261011/cpu-validation.json),
[regression tests](../overlay-moe-boundary/test_router_padding.py),
[diagnosis closeout](root-cause-closeout.md).
