# Bounded preparation and windows

No device window is run by the preparation agent. Every window refuses launch
unless expected seconds plus 17 is at most one quarter of its watchdog.
See k2-duration-plan.json for arithmetic and measured packet38 inputs.

K2 planning reservations: capacity 4096 297 seconds; capacity 32768 1840 seconds.
The 32K reservation includes quadratic growth of the current stable-rank
selector, inferred from measured short-shape cost. These are conservative
reservations, not measured long-context timings. Both fit a 10800-second watchdog
(quarter 2700); shorter watchdogs below 1256/7428 seconds are refused respectively.
The historical repaired packet38 K2 was roughly four minutes at short context.
No range of 66 lengths is registered here.

Each child has a bounded cancellation/stop channel. A failed experiment is not
retried. Wrapper storage/admission errors and coordinator stops do not latch a
GPU fault. A fresh kernel signature or failed owner with device-contact evidence
latches the boot and requires coordinator recovery. Children are stopped
cooperatively and retained if their bounded drain cannot finish.

Real CPU gates run serially: at most two rank processes, two OpenMP threads
per rank, nice 19 and idle I/O, inherited affinity. Compiles use at most two
concurrent single-job builds and do not overlap real-model gate execution.
