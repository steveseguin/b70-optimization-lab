# Retention and restoration

This directory copies packet64's engine source. It retains its needed include
closure and numerical headers; unused copied campaign Python entry points were
omitted. `parent-source-manifest.json` records the original copied inputs.
`instrumentation.patch` is the original packet56-to-57 observation delta used
as a porting reference; the final packet64 delta is `packet64-attribution.patch`.

`rope.bf16` is a **4 MiB deterministic rotary constant table**, byte-identical
to packet64's table. It is required by the engine and intentionally retained as
a large source artifact, not model weights or a generated cache. Its SHA256 is
bound by the build receipt. Restore it from this Git revision, or copy the
parent table and verify the recorded hash; do not recompute different constants.

`build/` is ignored, local CPU preparation output. It includes host/device
binaries, checked-source mirrors, serial compiler objects/logs and synthetic
miniature fixtures. Inherited compiler objects are immutable hardlinks;
only the local entry object is rebuilt. Neither compiler objects nor inherited
source trees are modified through the hardlinks. Initial construction receipts
are preserved locally under `build/initial-*`; final receipts in the packet
are authoritative. No model payload was read or copied.

To restore missing builds, use a fresh copy of this packet at the same absolute
path, with no existing build receipt or seals, while preserving any old evidence.
First restore packet64's retained objects under their recorded paths. Then:

```bash
P=experiments/own-xpu-runtime/stage2/packet64-attribution
mkdir -p "$P/build" "$P/evidence"
cp experiments/own-xpu-runtime/stage2/packet64-record-bundle/build/fusion-rope.hpp "$P/build/fusion-rope.hpp"
OMP_NUM_THREADS=2 nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/build_engine.py" < /dev/null
OMP_NUM_THREADS=2 nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/cpu_gate.py" < /dev/null
OMP_NUM_THREADS=2 nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/reset_gate.py" < /dev/null
OMP_NUM_THREADS=2 nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/seal_packet.py" < /dev/null
```

Rebuilds require fresh candidate and wrapper seals; they are not substitutes
for retained binary hashes. This is an originating-host lab screen, not a
portable published recipe. Never overwrite a sealed candidate being run by
the coordinator. All device evidence stays in the wrapper's fresh output tree.
