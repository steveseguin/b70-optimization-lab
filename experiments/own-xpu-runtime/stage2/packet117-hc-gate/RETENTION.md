# Packet117 retention

`rope.bf16` is a 4,194,304-byte exact copy of frozen
`../packet110-class-roofline/rope.bf16`. The copied whole-layer harness opens
this packet-local table when constructing its QSA fixture. Retain it with the
source because the strict wrapper identity checker rejects symlinks and the
micro must reconstruct the same input bytes without an originating binary.
The source and seal carry its SHA-256. Restore by copying that frozen table
and checking `seal.json`; do not regenerate trigonometric values.

All binaries, objects, compiler temporary files and checked include mirrors are
ignored under each build directory. Rebuild from `build_cpu.py`,
`build_layer.py --mode device`, `build_layer.py --mode gnu-host`, and
`build_image.py`, using the commands in the work note. Frozen packet97 linked
objects are verified by a byte-identical parent relink; their source/build
recipe remains in that frozen packet. This is a local lab experiment, not a
published clean-host deployment recipe.

Compact compiler dumps, CPU raw-byte gzip evidence, failed candidate bytes,
CPU and queue receipts are retained. The rejected unconditional epilogue is
historical evidence, not an alternate qualified candidate. No existing source,
raw evidence or frozen packet is removed by this preparation.
