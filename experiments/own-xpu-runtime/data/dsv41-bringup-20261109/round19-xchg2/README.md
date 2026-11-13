# Round 19, xchg2: decode / check exchanges as one-peer-at-a-time pushes (2026-11-12/13)

Helper xchg2 (`/home/steve/dsv41-work/xchg2/`). Patch `xchg2-1.patch`: `OWN_XPUSH2=1` (opt-in, default off).

## Bench (`engine/tools/bench/xchg2_lat_bench.cpp`, built as `xlat`; `xlat1.txt`, `xlat2.txt`, tables `*-table.txt`)

Six cards, the engine's transport (one context per card, IPC peers as direct kernel arguments, flags in the
receiver's own memory, bounded spins + poison). Every round on every card: producer (16 groups) -> exchange ->
consumer that checks every float; regions alternate. Number = round time minus the no-exchange round, us, mean of two
passes, 600 rounds each. "even": all producers alike; "heavy": cards 2 / 5 ~10 us later (output-a's real shape).
Every value exact in every configuration (0 wrong floats, 0 timeouts, journal clean).

Payloads per card (engine layouts): H = 848-864 floats x M slots; OA = 1024 / 2048 floats (8 / 16 heads) x M;
ACT = 384 floats x 7 M slots (stride 2304).

| exchange | today | today's form | best new form | new | saving |
|---|---|---|---|---|---|
| OA, 1 token (decode) | pull | 10.3 / 9.5 | XchgP (one group, all peers) | 5.8 / 5.6 | 4.5 / 3.9 |
| ACT, 1 token (decode) | pull | 10.9 / 9.6 | XchgQ 4 groups, no lockstep | 8.1 / 7.6 | 2.8 / 2.0 |
| H, 2 tokens | XchgPushM | 13.7 / 11.0 | XchgQ no lockstep | 7.9 / 7.4 | 5.7 / 3.6 |
| H, 3 tokens | pull | 13.5 / 12.5 | XchgQ no lockstep | 8.1 / 7.7 | 5.3 / 4.8 |
| H, 4 tokens | pull | 13.6 / 12.6 | XchgQ no lockstep | 8.4 / 8.0 | 5.2 / 4.7 |
| H, 5 tokens | pull | 15.0 / 13.7 | XchgQ lockstep (sk4) | 11.0 / 10.7 | 3.9 / 3.0 |
| H, 6 tokens | pull | 15.2 / 13.7 | XchgQ lockstep (sk4) | 11.3 / 10.8 | 3.9 / 2.8 |
| OA, 2 tokens | pull | 11.1 / 9.9 | XchgQ no lockstep | 8.1 / 7.5 | 3.0 / 2.4 |
| OA, 3-6 tokens | pull | 11.9-15.3 / 10.2-12.9 | sk4 | 10.5-13.8 / 10.2-13.3 | 1.4-1.9 / -0.7-0.2 (off by default) |
| ACT, 2-3 tokens | pull | 12.6-14.3 / 10.9-12.3 | sk4 | 11.3-12.2 / 10.7-11.6 | 1.4-2.1 / 0.2-0.6 (off by default) |

(x / y = even / heavy.) Floor (flags only, no data): 4.1-4.3 / 3.6-3.7 us.

What the bench shows:
- XchgP (one group, every item to all five peers) is the fastest while each receiver gets under ~30 KB per exchange
  (OA at 1 token: 28 KB); above that it falls off a cliff (H at 2 tokens 12.0, ACT at 1 token 12.5, ACT at 6: 173).
- Several groups each writing to all peers (XchgPushM) is the slow pattern at every size (H at 2: 13.7; ACT at 6: 304).
- Peer-ordered pushes (card c writes to c + 1, c + 2, ...: each card also receives from one sender at a time) win from
  ~7 KB per card. Four groups with no lockstep are best while each item stores at most one vec4 per peer (up to 1024
  vec4 per card); beyond that the groups drift onto different peers (snk4 at ACT 4-6 tokens: 89-118 us) and need the
  on-card lockstep (sk4: robust everywhere). Eight groups in lockstep fail at ACT 5-6 (92-145 us).
- Five launches per exchange (one per peer) pay ~2.5 us per launch at these sizes (13-16 us); the producer's last
  group pushing (no launch) is no faster than a separate one-group launch.
