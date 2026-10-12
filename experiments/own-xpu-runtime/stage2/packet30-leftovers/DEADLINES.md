# Expected duration and safety budgets

These are planning estimates, not a speed result and not a kill deadline.
K0 expects30s work plus17s first compilation (47s total); watchdog300s.
G3 expects400s work across two owners plus17s first compilation each (434s total);
watchdog1736s by default. Every watchdog is at least4x its estimate and300s.
Overrides below that floor are rejected before a latch or device discovery.

Each native submission has a300s wait budget, separately from a10ms planning
estimate for an ordinary event. The wrapper records both; the short estimate
never becomes a kill deadline. Host compilation/process address space is capped
at8GiB, one job per build invocation and at most two concurrent compile jobs.

The wrapper polls the kernel journal every250ms and stops new work on the first
specific GPU fault signature. It persists failure first, sends SIGTERM to the
owner, permits60s cooperative drain, and retains a still-busy owner for the
coordinator instead of hard-killing it. Postflight watches another5s. Timeout,
failed exactness and compiler exceptions are distinct from measured performance.
No server/device action ran during this CPU-only preparation.
