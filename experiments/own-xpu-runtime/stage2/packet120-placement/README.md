# Packet120: target placement 24/24 versus 25/23

CPU preparation of packet118 bundle7 on a frozen source copy. The two views
have identical arithmetic and selection: wide64+halfcache, down tile16,
rec-both-plus, other-fusion, split target head, draft prefix 80,128, rank1
draft and 4096-token BF16 KV. Only target layer24 and its transfer boundary
move to rank0. `placement=1` is 24/24; `placement=25-23` passes target split25.

[Census](evidence/census-first.json): rank0/rank1 device allocation is
29,276,806,152 / 30,296,914,384 bytes for 25/23. This leaves
2,935,448,568 / 1,915,340,336 bytes in the unchanged 30 GiB arena.
No expert offload, cache precision or head suffix adjustment is required.
The half-cache is an expanded **device** expert layout. Graph-static allocation
requests are zero in this engine's census; driver/library pools remain unknown.
The device worker records per-process DRM counters separately from allocator
bytes at READY and after the suite. Neither is presented as global free VRAM.

The **lane-B v4 bracket** is production / 25-23 / production, three fresh
process pairs, twelve cold prompts × 128 tokens per process pair, plus the
inherited reset-separated incident64 gate. Every token must equal
`iq3-p49-split32-v1`; acceptance must be identical across placements and repeats.
At least +0.5% over **both** controls admits the conditional lane-A confirm
bracket. The same +0.5% requirement applies on A. v5 switching is not allowed
for this allocation/topology change. The twelve-prompt screen is diagnostic;
full natural completion/strict512 promotion remains outside this packet.

Proposals are new files only: [B grid](../../ops/lane-queue/proposed-p120-B.txt)
and [A confirm](../../ops/lane-queue/proposed-p120-A.txt). A waiter may hand over
the A proposal only after B passes. The A entry also enforces that prerequisite
at execution, before any device work. This preparation launches neither lane.
`bracket_report.py --lane B|A` reads complete, hash-bound receipts and reports
hit/miss means, each rank's command costs, acceptance and the exact gain gate.

The brief's +3% hypothesis is not a measurement. Packet108's roughly 0.52 ms
race slack is shared between lengthening rank0 and shortening rank1; the
1.78 ms draft wait is not additional target-race slack. A whole-layer move can
cross that race and make misses slower. The bracket decides.

CPU preparation (from this folder, nice19 / CPUs8–15,24–31 / Python-B / stdin
closed; CPU entry-only 8 GiB limit; packet94 serial compiler turn):

```
python3 -B cpu_prepare.py build_engine.py cpu_gate.py full_shape.py prepare_chain.py startup103.py source_audit.py test_gates.py prepare_packet.py
```

Then run `launch_limit_gate.py` from an **uncapped** CPU process: its audit
prohibits native execution/device opens and intercepts both actual rank exec
points. Its isolated negative child installs the forbidden inherited cap.
Finally `cpu_prepare.py queue_plan.py retain_build.py` checks proposals on
private queue copies and retains generated source evidence. Only the entries
in this README are packet120 workflow; the copied ancestor orchestration and
submission helpers are historical implementation context, not launch commands.

[Work note](../../../../notes/2026-10-18-own-runtime-packet120.md),
[boundaries](DO-NOT-REPEAT.md), [retention](RETENTION.md),
[CPU preparation closeout](CPU-PREPARATION-CLOSEOUT.md).
