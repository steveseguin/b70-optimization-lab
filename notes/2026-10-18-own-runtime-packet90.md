# Packet90 — prepare exact expert and HC candidates

CPU-only work started before packet86’s verdict. The diagnostic can separate
some decoding and repeated-read costs, but its table lookup test cannot identify
launch overhead and its old HC control differs from packet84’s current geometry.
The [preregistration](../experiments/own-xpu-runtime/stage2/packet90-expert-hc/PREREGISTRATION.md)
records every verdict, candidate order, expected budget and risk.

First choices: decode IQ2 gate/up half scales once at load; prepare exact FP32
HC gate weights once at load. Both keep the original ordered arithmetic and
have separate memory admission. Builds, byte gates, startup and seals pending.

`git pull --rebase` was attempted first and refused existing dirty live logs.
Read-only fetch confirmed HEAD and origin/main equal, so no stash/rebase or
foreign edit was needed. Existing packets, shared screen and live ops are frozen.
Only new proposed queue files may be written. No GPU/service/host-setting work.
