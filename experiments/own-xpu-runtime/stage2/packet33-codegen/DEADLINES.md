# Bounded work and window deadlines

Packet33 CPU preparation is complete to the documented analysis scope. No
GPU reservation was consumed. Compilers run serially (at most2 permitted),
nice19 / idle I/O / OMP2. The8GB anonymous-memory ceiling applies to rebuilds too.

| Stage | Expectation only | Abort boundary |
|---|---:|---|
| Coordinator K0 compile smoke |60s|300s watchdog; no retry|
| Coordinator K2 diagnostics |180s|720s watchdog; no retry|
| Cooperative drain after K2 stop |usually one completed repetition|360s then retain PID and report failure|

Do not shorten watchdogs to these expected times. The prepared harness has
not supplied observed startup/timing durations. Any GPU fault belongs to the
coordinator's evidence-first recovery workflow, not to this CPU packet.

Analysis limits remain explicit: exhaustive dynamic instruction/message counts
for every variable path, a measured launch floor, and an accurate transferable
cost model are not established. This packet does not disguise static counts as
those results. A subsequent study can trace the selected paths and use matched
runtime-option receipts; neither requires changing the arithmetic identity.
