# Packet58t: resident one-card lookup bytes

CPU-only work on main. Pull refused unrelated dirty orchestration files;
fetch confirmed HEAD == origin/main at `6bf515a44f200e14d24ede24a398d2c3aea024bc`.
The work uses a new `stage2/packet58t-resident-lookups/` copy. Existing packets,
screens and ops are frozen; only a new proposed queue file may be added.

The host preparation path reads one token embedding row and sixteen PLE rows
from two GGUF tensors. Together they occupy 29.32 GB but supply only 3,540
packed bytes per token. Experts already use pinned memory. The
[analysis](../experiments/own-xpu-runtime/stage2/packet58t-resident-lookups/ANALYSIS.md)
and [source-bound census](../experiments/own-xpu-runtime/stage2/packet58t-resident-lookups/evidence/lookup-inventory.json)
record exact bytes, offsets, scales and access pattern without model reads.

Implementation and CPU validation are in progress. The candidate uses exact,
read-only anonymous copies at load; device parity, full-size allocation and
speed remain pending. All work uses nice19, helper cores and Python -B, with
no GPU, service, sudo, settings change or live queue edit.
