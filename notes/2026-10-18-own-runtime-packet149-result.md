# Packet149 result: per-layer exchanges for a shared miss correction cost ~9 ms/miss in-engine; shared correction closed

Output-neutral probe, one-load v5 bracket `packet149-xchg-bracket-B`, lane B, 23:13–23:21 UTC October 18, fault count 2. Smoke passed 23:11. Evidence: `stage2/packet149-shared-correction-probe/v5/evidence/device-xchg-v5-B/` (`bracket-summary.json`, `run/views/*/summary.json`). The fixed report reader worked.

| View | Mode | tok/s | Exact |
| --- | --- | ---: | --- |
| 00 | off | 58.702 | 13/13 |
| 01 | xchg | 52.684 | 13/13 |
| 02 | off | 58.679 | 13/13 |
| 03 | xchg | 52.669 | 13/13 |
| 04 | off | 58.694 | 13/13 |

`xchg` adds, during corrected first halves only, the real per-layer payload exchanges a cooperative row split would need (payloads discarded; outputs unchanged). It costs **−10.3%**: about 17.04 → 18.98 ms/token, +1.95 ms/token on average. With ~21.5% of intervals missing (256/1188), that is **≈ 9 ms of exchange cost per miss**. The whole correction is 11.8 ms, and a shared correction would need the exchanges to cost ≤ ~1 ms/miss to net the 2–3 ms that packet147 rank 7 priced.

Decision: the shared-correction line (packets 144, 147 rank 7, 148) is **closed on device evidence**. Per-layer cross-card synchronization in the serial correction path is far too expensive on this PCIe topology. packet150's conditional prototype (a) does not proceed. Its (b) probe, the rank-0 out-of-layer split on the current build, continues.
