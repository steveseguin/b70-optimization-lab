# Packet117: parallel independent HC sigmoid products

See the [work note](../../../../notes/2026-10-18-own-runtime-packet117.md)
for source analysis, closed-arm distinctions and current status.
The source keeps production Q8 paired-row loads and all original FP32 sum
chains/trees. It distributes independent sigmoid products over existing
subgroup lanes and preserves ordered final mixing.

CPU-only preparation. No device equality or speed is claimed. The copied
packet110 whole-layer micro must reach <=0.70× production for both HC sites,
both QSA/GDN layers, both orders and two fresh processes before the
[conditional v5 bracket](v5/README.md) can run. No live queue is edited.
