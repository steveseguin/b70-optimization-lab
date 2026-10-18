# Packet58p: tile16-only one-card chain prepared ahead of the screen

October 18, CPU-only, main. The initial pull refused unrelated dirty
orchestration files; fetch confirmed HEAD and origin/main both at
`62eaf3c3cd1fc0c5d83cbc7115da08259027c9fb`. Those files, every existing packet,
screen and ops tree, and live queues were preserved. The work uses a new
`stage2/packet58p-onecard-record/` only, plus this note and CURRENT.md.

The new chain copies packet58m's seven-window machinery and packet58n's exact
tile16-only selection. Route stays route-exp32-rank4, recurrence rows4-shared,
HC production. The device binaries come directly from 58n, byte-identical;
the three CPU binaries come from 58m. Nothing was compiled. The build is
**72,734,584 bytes**. The prior record remains **24.338653323339745 tok/s**,
submission `cmvd8bhou000duj01hxaihg15`; no new speed is claimed.

All **118 Python tests**, **12 complete Python argument paths**, **10 native
parser/oracle checks**, **10 full-shape startup/submit checks**, **48 K1 byte
checks** and **seven host/VRAM budget checks** pass. Both copied drain gates
have the nonnegative clamp; `scripts/check_drain_fix.py` reports **2 FIXED,
0 UNFIXED**. The old clock-crossing failure is reproduced in memory. The
selection tests refuse missing or extra keys and either of the unwanted port
levers. A read-only delegated audit found no preparation blocker.

The argument gate follows actual queue commands through window.main and then
suite_driver.main to intercepted native execution, for every chain window and
both model miss paths. Only operational prerequisites, leases and live host
state are synthetic. Selection validation, oracle bindings, prompt tables,
memory admission arithmetic, device-mask validation, retention and native argv
assembly execute normally. Its audit hook denies subprocess execution, GPU
and model-payload opens, and writes outside scratch. No fabricated output
enters the actual chain evidence directory.

Every queue/window/native launch checks getrlimit against its import-time
snapshot and refuses finite address-space limits or any limit change. Limits
are never installed by imported modules. The tiny argument process stays
uncapped in address space to exercise that real pre-exec check. An attempted
8 GiB AS cap on the CPU full-shape mock failed at `fullshape mmap`: its sparse
virtual arenas reserve full production extents without touching that much RAM.
The full-shape gate therefore checks actual peak RSS instead. The largest
recorded gate child RSS is **63,082,496 bytes**; K1 runs under its CPU-only
8 GiB CLI cap. This was a CPU refusal, not a GPU fault.

All budgets match 58g. Timing requires **118,308,908,048 bytes available**,
including an unchanged **109,718,973,456-byte host bound** and 8 GiB reserve.
Full BF16 KV, target-only decode, the 18 GB immutable expert cache, packet49
oracle and 128-token scope stay fixed. Every window reserves the whole host.
The coordinator must pause and drain lane B and keep it paused through gaps.
Only WS128 is timed; WS128x remains exactness-only. A second timing run and
the strict 512-token final gate are still missing.

Submission tooling was finalized before sealing. It omits `specNumTokens`,
discloses target-only tile16 down layout and host-pinned weights, and keeps the
same oracle and 128-token limitations. The historical 58g v3 result parses and
replays at its exact saved rate, with submission eligibility false. The live
record threshold remains unchanged and outside the immutable build seal.

The preparation/tooling commit is `36ff94065`, pushed immediately. The final
seal names that committed source revision and verifies **277 immutable
inputs**. Build → submission-pins binding is one-way. A private source snapshot
reads 58n's original screen receipts at readiness time; mutable parent outputs
are not build-seal pins. The synthetic rule admits exactly 0.5% over each
control, refuses 0.496%, and also refuses missing arms or any inexact token.

At handoff, production-before is complete, down-tile16 has completed both K1s
and is in WSCREEN, and production-after has no queue receipt. **ready.json is
false.** The real verifier refuses the incomplete bracket and must reread all
three arms before the coordinator launches anything. No saved ready flag
bypasses it. It additionally verifies native binaries, exact selection, one
boot, fresh owners, matched miss paths, control drift and the prior record.

The [exact systemd command](../experiments/own-xpu-runtime/stage2/packet58p-onecard-record/WINDOW.md)
uses the 58g unit form and a fresh output directory. It is emitted only. The
coordinator alone supplies the fresh fault review and pauses lane B. The
seven-window passive plan passes without creating chain output or a fault
capture. Root free space at the final plan is **34,237,857,792 bytes**; planned
writes are 2,952,790,016 bytes. The 25 GB preparation stop floor was maintained.
The largest tracked artifact is 912,380 bytes; native builds remain ignored.

[Packet and reproduction](../experiments/own-xpu-runtime/stage2/packet58p-onecard-record/README.md),
[readiness and emitted command](../experiments/own-xpu-runtime/stage2/packet58p-onecard-record/ready.json),
[argument evidence](../experiments/own-xpu-runtime/stage2/packet58p-onecard-record/evidence/argument-gate.json),
[CPU closeout](../experiments/own-xpu-runtime/stage2/packet58p-onecard-record/CPU-PREPARATION-CLOSEOUT.md).

No GPU job, service, sudo, power/memory/swap/page-cache change, reboot, kill,
live queue edit, external API call or submission was performed. All CPU work
used nice19 and helper cores; Python used -B. No model server was started.
