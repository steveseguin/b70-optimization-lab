# D60 preregistration: repaired TP2/MTP0 strict replay

Date: 2026-08-31

D59r passed the complete performance workload, cached-token, canary, shutdown,
and fault gates at 17.896698 tok/s and 195.835491 ms median TTFT. It failed the
preregistered cross-TP exact-output requirement: six prompts matched TP1 D54
exactly; six differed (first differences at tokens 60, 181, 182, 437, 450, and
455). Objective quality canaries all passed. Different TP reduction arithmetic
is not by itself evidence of quality loss, but D59r cannot be promoted under its
original cross-TP gate.

D60 freezes D59r as a TP2-specific comparator and repeats the exact bounded
TP2 configuration in a new process/cache. All twelve complete token-ID streams
must equal D59r, in addition to every strict workload, cache, canary, shutdown,
and fault gate. A pass establishes a deterministic repaired TP2/MTP0 baseline;
it does not make the slow target-only rate a speed recommendation. The next
authorized experiment is MTP restoration compared against this TP2 baseline.
