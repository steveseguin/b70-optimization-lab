# Packet 34 deadlines

Expected total duration is 300 seconds for planning only. It is not a timeout,
a speed result or a promise about cold compilation. Both coordinator windows
default to a 1,200-second watchdog; the wrapper refuses values below
`max(300, 4 * 300) = 1,200` seconds. Native expected time is not used as a failure
boundary. The benchmark's internal campaign guard is 1,800 seconds, while the
coordinator wrapper provides the enclosing watchdog.

Direct mode checks every completed kernel's profiling interval against a
4-second per-kernel device budget. An invalid or over-budget event fails the
measurement. The runtime's native wait budget is 60 seconds. These limits are
safety limits, not expected latencies and not measured speed claims.

A whole-half graph is one host submission; the layer variant submits 24 graphs
in order. The complete submitted graph sequence has a 60-second completion
budget, which also bounds each of its constituent submissions' completion.
Checking the budget does not interrupt GPU execution. If completion is not
proven, admission stops and ownership stays alive. Host wall and thread CPU
measurements include the first issue through host-observed completion.

On a fault, interrupt, journal failure or watchdog expiry, R1 writes the wrapper
failure and boot latch before requesting cooperative SIGTERM once. It allows
60 seconds for draining. A still-busy native child is retained and the wrapper
returns status 75; it never escalates to SIGKILL or driver reset. Journal helpers
have two-second bounds, ldd has a ten-second bound, and postflight watches the
journal for five seconds after child exit. A failure reported after work or
normal teardown still prevents a passing window.

K0 submits no kernels. Its unchanged compile-smoke program has no cooperative
signal handler, so the wrapper never sends it SIGTERM. On a stop condition it
records failure and retains the compiling child for the coordinator. Native
compilation must return before the owner can be released; it is never killed.

The wrapper records inherited CPU affinity and nice value and never changes
either for the native child. A nice-0 coordinator may start R1 under taskset on
its reserved cores. Preparatory CPU agents continue at nice 19 on their inherited
affinity. ldd and journal helper processes use nice 19 and idle I/O priority.
No power, host memory, swap or page-cache setting is changed.

Native recording, optional driver-memory queries and teardown errors are saved
before cleanup. An uncertain enqueue keeps graph, event, allocation, queue and
context owners alive. A failed native cleanup is never retried. Memory-growth
and device-fault evidence remains in native/recording/kernel logs even when the
coordinator must retain the child.

The memory watcher samples the native process tree on each supervision loop
(250 ms sleep plus journal-read time). It uses `/proc` reads only and stops at
7.5 GiB of summed RssAnon, leaving 512 MiB of headroom below 8 GiB. Sampling
cannot guarantee a hard cap between polls; there is no cgroup/host-memory setting
change. Sensor failure takes the same fail-closed stop path. Peak usage and the
last process list are retained in the receipt before any cooperative stop.
