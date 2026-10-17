# Packet53b: more logical lanes, unchanged sums

CPU-only preparation of V4/V8/V16 experts, V2/V4/V8 HC low/gate and V2/V4
small FFN. The two HC sides form one class and share one selected V.
The coordinator owns GPU qualification. No model oracle is started.

- [Preregistration](PREREGISTRATION.md) and [machine manifest](manifest.json)
- [Kernel design and proof](KERNEL-DESIGN.md)
- [CPU build and gates](CPU-BUILD.md)
- [Coordinator commands](WINDOW.md)
- [Engine call-site map](INTEGRATION.md)
- [Negative-result index](DO-NOT-REPEAT.md)

The baseline is packet49c production, not packet53 V4. Both timing owners
must save at least 35 µs per ordinary M1 layer with one common selection.
No model throughput claim or engine integration follows from CPU tests.
