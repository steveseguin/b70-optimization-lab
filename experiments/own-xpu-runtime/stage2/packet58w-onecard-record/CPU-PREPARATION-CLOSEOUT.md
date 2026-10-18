# Packet58w one-card record preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Can the packet58p seven-window chain safely qualify packet58v's tile16 plus
overlapped cache maintenance without another rebuild? October 18, 2026;
one B70, Unsloth UD-IQ3_XXS revision 766911a6b7369840a91dbcd95f9f997acaab6cd6,
target-only, packet49 arithmetic, 18 GB immutable expert cache, zero-copy
misses, host-pinned experts and context4096 BF16 KV. Preparation is CPU only.

## Outcome

The chain, conditional readiness reader and submission tool are prepared.
No device run or speed improvement is claimed. The one-card record remains
26.22859930943809 tok/s. Device readiness requires the actual 58v smoke and
five-view bracket, with both overlap views at least 0.5% above every serial
control and no more than 3% control drift.

## What worked

The reused binary accepts every chain window with `--cache-maintenance overlap`
without a bracket table or rebuild. Full-shape startup, K1 mixed-source bytes,
postload census and the original oracle consumer pass. Every entry is replayed
through the real unit, environment, topology, memory and argument gates, with
native exec intercepted. Wrong units and extra environment variables refuse.
Submission tests replay the whole evidence chain and exercise the shared CLI
with network forbidden.

## What failed or remains uncertain

Copied tests exposed old admission expectations and a default helper that
still returned the historical budget. The new default matches the measured
per-window policy; the tests now exercise its exact byte boundary. Initial
adaptation failures are retained in the orchestration log. No device fault was
caused or recovered here. CPU mocks cannot establish overlap device exactness,
queue behavior or speed. The forthcoming 58v runs and fresh 58w chain must do so.

## Evidence and patches

[Entry paths](evidence/argument-gate.json),
[startup and oracle replay](evidence/startup-cpu.json),
[full shape](evidence/fullshape-submit-cpu.json), [K1 bytes](k1-cpu.json),
[tests](evidence/python-cpu-gates.json), [budgets](evidence/budget-cpu.json),
[drain scanner](evidence/drain-fix.json), [literal audit](evidence/literal-audit.json),
[copy manifest](copy-manifest.json), [restore helper](restore_build.py),
[initial adaptation tests](../../ops/packet58w-orchestration/initial-tests.log),
[work note](../../../../notes/2026-10-18-own-runtime-packet58w.md).
All changed code is local to this packet; frozen parents remain intact.

## When to revisit

The coordinator may run the sealed command only after the parent smoke and
bracket pass the recomputed gate. Failed device evidence requires a separately
recorded decision or new packet; it cannot be repaired by resealing this chain
once its output exists. A second fresh timing run and strict512 evidence remain
separate unresolved gates, regardless of the later 128-token result.
