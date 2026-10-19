# Coordinator contract

- CPU preparation only. Never insert these rows into a live queue automatically.
- Use `proposed-p58aq-split-A.txt`, lane A/card 0, whole host, PAUSE-B held.
- Check final `READY-FOR-DEVICE.json` and the sealed build. Freeze CPU preparation
  before the model window; no GGUF/full-shape reads overlap timing.
- K1a, K1b and one WSCREEN run once. No retry or service restoration.
- WSCREEN has A0/U0/S0/D0/W0/A1, all twelve fixed prompts, 32 tokens, one load.
  All views reset prompt state and begin with empty expert-cache residency.
- The optional `proposed-p58aq-smoke-A.txt` is a separate 12 x 64 control smoke;
  do not add it to the split by default. The split has its own opening control.
- Keep resident lookups, full BF16 KV, maximum cache and the complete 58aj line.
- Publication skip probes repair the table and drain before model readers.
  They never claim speed. Oracle mismatch stops the run and drains the owner.
- No data-proof timeout. Native operations allow 600 seconds each; safety
  watchdog remains 7200 seconds. Watch faults and use inherited graceful drain.
- Admit 98,990,252,032 bytes host available including 8 GiB reserve. Reserve
  25 GB root free after writes: 100 MB split, 50 MB optional smoke.
- Consume `WSCREEN/run/summary.json`; retain controls, drift, call counts,
  per-operation wait stamps and separate repair cost. The summary emits the
  conditional build brief, host-work note, or negative row. Missing measurements
  and unmatched cadence are inconclusive, not a closed optimization lever.
