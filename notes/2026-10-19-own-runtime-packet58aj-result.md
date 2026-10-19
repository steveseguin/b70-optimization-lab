# Packet58aj result: resident lookup tables are exact and +1.27–1.59% faster on the one-card record line

Card 0, one whole-host session (`fn-run/hold-onecard4.sh`), 2026-10-19:
- smoke `packet58ajb-smoke-A` 03:08–03:16 UTC, exact;
- one-load v5 `packet58ajb-v5-A` 03:18–03:33 UTC.

The line is packet58ah (the 31.663 tok/s record line) with every row of `token_embd` and `per_layer_token_embd` (29.3 GB) copied into anonymous memory at load, SHA256-verified. There is no page-cache advice, no mlock and no setting change. The first-operation wait limit is 300 s: the first smoke had failed on 60 s.

| View | Lookups | tok/s (class-balanced) |
| --- | --- | ---: |
| A0 | mapped | 26.928 (cold warm-up; reported, excluded) |
| B0 | **resident** | **31.959** |
| A1 | mapped | 31.558 |
| B1 | **resident** | **32.061** |
| A2 | mapped | 31.525 |

- All 60 prompt checks are exact. Warm control drift is 0.105%.
- Resident beats every warm control by **+1.27% to +1.70%** (minimum +1.27%).
- Packet58t found resident lookups neutral (−0.16%) on the older tile16 line. On today's faster line the mapped tables' page faults cost more.
- The readiness wording ("within ±0.5% of every control") came from a coordinator brief whose intent was non-inferiority. Codex p58ajc amends it to "≥ −0.5% vs every warm control", disclosed, and completes the record-chain handoff.
- Because both lanes are idle, the lab rule allows a record chain below +2% (projected ≈ 32.0 tok/s). The chain's WS128 must still beat 31.662719 for a submission. Resident tables should also stop the 5–8% WS128 paging losses seen in chains 58w-a and 58ah-a.

Evidence: `experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/screen/evidence/card0-58ajb-screen-a/resident/WSCREEN/summary.json`.

## Record chain (submitted)

The chain `packet58-onecard-58aj-a` ran 03:40–04:15 UTC; all seven windows passed and were exact.

| Window | tok/s | Major faults |
| --- | ---: | ---: |
| WS128x | 31.975 | 1,716 |
| **WS128** | **31.967** | 0 |

- The two windows agree within 0.03% despite the faults, so the line is paging-immune.
- **Submitted** 04:18 UTC: `cmveqsmsl00ebrf014yvrsosx`, APPROVED, +0.96% over 31.662719. Receipt in `data/localmaxxing-responses/2026-10-19-packet58aj-chain-a-onecard-ws128.txt`.
