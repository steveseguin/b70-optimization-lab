# Packet58ag: remaining one-card target ports

CPU preparation, bounded to three hours from 2026-10-18 23:06 UTC. No device
execution, service, live queue edit or performance claim. Packet58ab is copied
with symlinks preserved; existing packet trees remain frozen.

HC fusion remains enabled in both controls and candidates. The new runtime
dimensions default to production: `hc_geometry=production|hc-wide`,
`experts=production|wide64+halfcache`, and `other_fusion=production|fused`.
The inherited bracket token `p60fusion` names the full composition in this
packet only; it does not mean HC fusion is off in its production controls.
The smoke runs 12 × 64. The combined five-view bracket runs 12 × 128 per view,
one load: control/candidate/control/candidate/control. A0 must be exact but is
excluded from drift and speed comparison under the packet58wb rule.

The halfcache port uses an exhaustive 65,536-entry exact FP32 half-decode
table (262,144 device bytes), rather than packet90's larger packed weight rows.
This preserves the one-card cache's weight layout, expert pointers, tile16,
capacity and fill policy. It is an adaptation, not the original layout.
The fused router includes route-fast as an inseparable part of packet109's
implementation; there is no repeat of packet58r's standalone route arm.

All output must match `iq3-p49-split32-v1`. CPU bytes, device exactness and
speed remain separate gates. READY is absent until the final write.

See [audit](AUDIT.md) and [work note](../../../../notes/2026-10-18-own-runtime-packet58ag.md).
