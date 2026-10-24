# Own XPU runtime engine: canonical source tree

This is the single source tree of our own model-specific B70 runtime. It starts from the exact files that
built the SC117 service binary `17c3c5c2…`.
- That engine had grown as a chain of packet overlays: copied `source-v2` trees, absolute `#include` paths and
  `#line`-pinned historical file names.
- [tools/consolidate.py](tools/consolidate.py) collapses that chain into `src/` under the logical paths the files
  always had, such as `stage2/packet194-expert-diet-engine/…` and `gsq-rco-iq3s/…`.
- Includes are relative to `src/`, and the `#line` directives are gone.
- The 45 duplicated copies were verified identical before merging.
- [build-manifest.json](build-manifest.json) records every file's origin and hash, the 40 translation units with their
  unchanged compile flags, and the link order.

Build (CPU only, never runs the binary):

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B build.py /dev/shm/engine-build --jobs 6 --name sc117-engine
```

Receipts of the binaries the service uses are in [receipts/](receipts/).

**Equivalence of the consolidation.**
- Binary `1fb6511b…` from this tree has 52 of 53 device images byte-identical to `17c3c5c2…`.
- The remaining image differs by one SPIR-V constant: the source line number that a device `assert()` records for its
  failure message, which moved because the `#line` directives were removed.
- Host code differs only by file paths.
- The LAN service's one-time B0 gate then proves tokens and full engine state byte-identical to engine 5926 on the GPUs.

**Direction (owner, 2026-10-24).** The engine will be reused for other models and kernels.
- New precision or features are added as typed, data-driven variants of existing kernel families, such as an
  activation type BF16|F32 chosen by the plan's buffer type.
- Tuned BF16 kernels stay selectable; nothing is forked or discarded.
- Batched prefill will be written once against those typed interfaces.
- The packet-named directories can be reorganized into modules gradually. Each move is a pure rename, proven by an
  identical build.
