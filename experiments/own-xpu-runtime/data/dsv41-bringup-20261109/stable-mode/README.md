# Stable mode for six-card DeepSeek runs (2026-11-15)

Owner, 2026-11-15: Codex's workaround "seems to have stopped it from happening consistently ... incorporate this
solution for now, so we can reliably progress with kernel optimization".

What it is (Codex, 2026-11-14 22:48 - 11-15 00:54, `/home/steve/diagnostics/serial-exchange-20261114T2248/`):
- BIOS 11.02 (owner update, 2026-11-14).
- The six GPU root links (CPU root ports 00 / 20 / 40 / 80 / a0 / e0:01.1) at Gen4 x16 instead of Gen5, through the
  kernel's PCIe link-speed cooling devices. Runtime-only: re-apply after every boot (`gen4.sh --apply`).
- `OWN_PX_SERIAL=1`: after each prompt exchange push a card waits (on its compute queue) until every peer's copy has
  landed, so prompt-exchange traffic and compute never overlap. Same queues, order and bits. Default in tp115+;
  `stable.env` exports it for older binaries.
- Default power limits (230 W; 275 W on 03 / 83).

Evidence: 54 fresh six-card starts (27 x34k + 27 x95k, 256 answers each, all the same as e82) in 118 minutes of model
work, no reset or fault. Before it: BIOS 10.06 + Gen4 reset on the 8th start, BIOS 11.02 + Gen4 (overlap on) on the
6th. Cost: prompt reading ~13 % slower (x34k 51.6 s vs 44.2, x95k 148.3 vs 128.1); writing about the same. Not a
root cause: fewer overlapping transfers could avoid a software race or marginal hardware under concurrent traffic.

Use: every six-card launcher sources `stable.env` and runs `preflight.sh` before work (BIOS, links, power, a clean
kernel log, memory; read-only; never while an engine runs: link reads are PCI config reads). Speeds compare only
within the stable mode. Not covered by the 54 starts (gated in c115): guessing, skip39 / index split, short prompts.
