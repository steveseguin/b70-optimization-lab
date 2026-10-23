# Device screen: qualified, October 23

The one-card instruction diet ran in one model load on card 0, 13:43–13:56 UTC including K1a/K1b and quiet intervals. Both fixture gates and the five-view model screen passed. Production/diet/production/diet/production rates were **36.579 / 37.573 / 36.599 / 37.583 / 36.601 tok/s**. Both diet views beat every control by at least **2.657%**. Warm-control drift was **0.00333%**.

All **60/60** cold 128-token responses matched the unchanged oracle. All views retained max23 capacity, full BF16 KV, resident lookups, kernel foreground I/O, and unchanged fills/bytes (13.457 fills and 26.678 MB per decode token). Diet views selected exactly 47 halfcache gate/up sites; layer 2 retained its other-layout kernel. No kill rule fired; teardown and window checks passed.

Attributed whole compute-window savings were **14.84 microseconds per layer**, from the control-minus-diet compute-window delta divided by 48. This is not a direct gate/up timer. The measurement agrees with the earlier 12–16 microsecond microbenchmark saving.

The screen and registered chain thresholds passed. This remains a **screen**, not a new record, full final quality gate, fresh-process repeat or LocalMaxxing submission. The retained one-card record remains 36.602512 tok/s pending separate record qualification. No public speed table or submission was changed.

[Structured result](evidence/device-screen-result.json) · [Summary](screen/evidence/card0-58de-v5-a/resident/WSCREEN/summary.json) · [Window](screen/evidence/card0-58de-v5-a/resident/WSCREEN/window.json) · [Raw retention manifest](evidence/device-screen-raw-manifest.json).

The original README and seal preserve the pre-run preparation identity. Current outcome and operational status are in this result and the dated repository note.
