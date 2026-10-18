# Packet95: exact expert grid prefetch

The E3 candidate moves the next IQ2 grid lookup ahead of current arithmetic.
It preserves production's step/chain/product order, independent gate/up sums,
adjacent reduction tree, BF16 stores and route/error behavior. No weight or KV
format changes. The current and next grid words are raw magnitude bits, never
an FP32 decoded cache. The code is copied from packet90; sources and accepted
production settings are pinned before packet86's pending verdict is read.

| View | Change | Extra modeled arena bytes, either rank |
| --- | --- | ---: |
| production | hc-wide, wide64, ordered, rec-parallel | 0 |
| exp-grid-prefetch | Next-tile dependent IQ2 table loads | 0 |

E2 is [closed by exact arena arithmetic](E2-CLOSEOUT.md), not an executable.
E5 is deferred in this time box. No blocked design is silently substituted by
production in a job. The full grid therefore contains production / E3 /
production. Both directions and separate E3-only grids have fresh output names.

[Preregistration](PREREGISTRATION.md), [coordinator handoff](WINDOW.md),
[CPU byte proof](evidence/cpu-byte-identity.json),
[E2 memory proof](evidence/e2-memory.json), and [boundaries](DO-NOT-REPEAT.md).
CPU passes do not establish GPU correctness or speed. No queue is live here.

[Linked code](LINKED-CODE.md) confirms the intended issue order without spills.
Driver/code residency and actual device latency remain unmeasured.
