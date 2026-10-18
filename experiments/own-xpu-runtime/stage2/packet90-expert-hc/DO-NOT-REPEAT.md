# Packet90 boundaries

- Do not confuse packet86's lookup grid with a launch grid, add ablation deltas,
  call onecached a DRAM/cache measurement, or copy its old HC cost to hc-wide.
- The record control is explicit: hc-wide, wide64, ordered, rec-parallel.
- No packet67 four-stream/roofline geometry, packet74 packed dense, packet81
  packed input load-count, or packet83 draft bytes are reopened.
- FP32 weight caches are exact immutable decodes, never compressed weights/KV.
- IQ4 half-cache expansion is excluded: it would add about 1.26 GB per rank and
  exceed the tight rank1 margin. IQ2 gate/up alone adds 315 MB.
- Combined caches and alternate native modes are not admitted. The loader and
  dispatch must agree on the 840-byte expert / 1280-byte HC row strides.
- Read full-size Arena censuses, not merely --plan success. Require negative
  short/misaligned allocation failures and unsupported-mode refusals.
- CPU exactness is not GPU exactness or speed. Every real screen starts with the
  shared 64-token oracle gate, then the full fixed 12-request suite.
- No live queue, existing packet, shared wrapper or coordinator work is edited.
