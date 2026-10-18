# Packet 103 chain a: WS refused by a drain-cooldown race; fresh folder b (2026-10-18)

`packet103-chain-a` (decision `1ad512f75aab3fce`, bundle 5) launched 09:16:54 UTC. K0, K1a, K1b, K2, W0p, KD (the window that failed packet 97's first chain) and W2m passed. **WS failed at admission, 09:53:23, before any device work**:

    drain_gate.py, line 51, in __enter__: self.sleep(min(.25, until - self.now()))
    ValueError: sleep length must be non-negative

The shared cooldown loop (`while now() < until: check(); sleep(min(.25, until - now()))`) re-reads the clock after `check()`, so the remainder can be negative. The loop only runs when a window starts within 60 s of the shared teardown record. Lane B's `packet115-micro-B-1` had completed its teardown at ~09:52:21, 24 s before WS. GPU fault count unchanged (2). The coordinator reviewed and archived the dead lane-A marker (no render holders, lock free, teardown drained).

The same line exists in 57 `drain_gate.py` copies (all bundles and the frozen v4/v5 wrappers). Packet 103 has no sealed resume pins, so the chain restarts in a **fresh folder `device-cards01-b`** with the same frozen decision, **with lane B paused** so no cross-lane teardown lands inside a window's cooldown. The chain's own 90 s gaps exceed the 60 s cooldown. New bundles (packet 118+) get `max(0.0, …)` plus a regression test.
