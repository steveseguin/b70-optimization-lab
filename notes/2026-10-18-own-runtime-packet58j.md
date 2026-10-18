# Packet58j: one-card target port

CPU preparation started from a separate copy of packet58g. The initial pull
refused existing unrelated edits; fetch confirmed local main equals origin/main.
No other work was stashed or changed. Frozen source hashes are retained.

Down-tile16 will transpose packed chunks at pin time, so both cache fills and
zero-copy misses see the same layout. Route-fast and rec-both-plus are selectable.
E1 adds 616,038,400 host-pinned bytes and is excluded under the unchanged
58g budget. No GPU, service or host setting is changed.

The port now passes all 80 full-size startup and submit checks: eight views,
five model windows, and both zero-copy and streamed misses. Each checks short
and full context and reproduces the old p28 pointer-table refusal. All 3,446
arena rows retain 24,287,732,980 device bytes and 48,633,091,712 pinned bytes,
including staging. All 56 view/window admission plans equal 58g.
Both GNU host and Intel device binaries compile. GNU and Intel each pass all
three raw-byte comparisons twice in fresh processes. Finite outputs agree
across compilers; 20 deliberately injected NaN recurrence cases preserve the
different payloads of each compiler's unchanged reference. No arithmetic or
NaN normalization was changed. Device execution is still pending.

The proposed bracket uses production / port / production, then a separate
fresh record chain only if it beats both controls and the saved record, with
controls within 3%. Every window holds the whole host and rejects lane B.

## Resumed after the authentication interruption

The source milestones were already committed as `7e4ec61af` and `84479d77c`.
The resumed session kept the uncommitted work, checked both build receipts and
the completed extent, memory, K1 and reset gates against their source hashes,
and reran only the unfinished byte gate and checks affected by wrapper fixes.
The shared checkout's unrelated edits again prevented `git pull --rebase`;
fetch confirmed that local main and origin/main matched. Nothing was stashed.

The campaign wrapper now records failure and returns a failing exit code when
the bracket or fresh confirmation loses. All 109 Python checks pass, including
mocked winning/losing campaigns and whole-host lane-B refusals. Cache-state,
expert-pointer, copy-queue contract, admission and passive card-mask checks
also pass. A stale test receipt was refused by the seal and regenerated from
the updated test; no gate hash was bypassed.

The final seal verifies 290 source inputs, both builds and all CPU gate
receipts. It excludes live queues and changing orchestration decisions.
The retained build is 160,667,337 logical bytes, below the 300 MB cap; the
byte-gate peak child RSS was 283,070,464 bytes. No GPU, service, live queue,
frozen packet or host setting was changed.

Coordinator handoff: [exact plan/launch commands](../experiments/own-xpu-runtime/stage2/packet58j-onecard-port/WINDOW.md),
[plan-only rehearsals](../experiments/own-xpu-runtime/stage2/packet58j-onecard-port/evidence/launch-plans.json),
[CPU closeout](../experiments/own-xpu-runtime/stage2/packet58j-onecard-port/CPU-PREPARATION-CLOSEOUT.md).
The two campaign plans and all eight view queues pass without creating a
device-output folder. The proposed record chain remains conditional on the
bracket. Its inherited 128-token cap keeps the strict 512-token gate false;
no external submission is performed or authorized by this CPU preparation.
