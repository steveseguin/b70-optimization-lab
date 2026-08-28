# Flash-Next TP4 eager MTP0 fixed-vision attempt 8 administrative closeout

Date: 2026-08-28

Attempt 8 ran only after the full frozen 900-second user-manager stability
window. After the external `sync`/drop-caches step, the exact sample was
111,788,592 KiB MemAvailable and 6,297,564 KiB SwapFree. The supervisor exited
1 at the initial-memory gate with `FAIL: less than 108 GiB host memory is
available`; the sample was 1,457,616 KiB below the 113,246,208-KiB floor.

The memory gate precedes evidence creation, card and collective health, the
launcher, and model work. No state or sentinel, run directory, supervisor
evidence directory, cache, compile directory, or RPC directory exists. Port
19687 remained closed; no launcher, model, worker, client, or request began.
This is a pre-admission administrative stop with no capability, quality,
speed, matrix, or website credit and no change to a protected result.

Attempt 9 changes only the one-time initial MemAvailable floor from 108 GiB to
105 GiB (110,100,480 KiB). Clean post-graph idle observations are around 106
GiB, while prior successful eager loading retained about 29 GiB MemAvailable.
The initial 6-GiB SwapFree gate and active-run 10-GiB MemAvailable / 5-GiB
SwapFree stop floors remain unchanged, as do every serving, performance,
quality, classifier, timeout, and teardown control. This administrative
admission treatment creates no performance claim.
