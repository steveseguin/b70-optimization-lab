# D62 preregistration: post-reboot synchronized TP2/MTP1 localization

Date: 2026-08-31

D61 failed before serving when the second B70 generated CCS page faults and
Xe reported `UR_RESULT_ERROR_DEVICE_LOST`. A function-level reset did not
recover it; no further GPU work is permitted in boot
`4136985e-4d03-45f1-8ecd-5b465b32e8d1`.

D62 may run only after a different host boot ID and clean, independent basic
compute gates on both B70s. It repeats D61's frozen TP2/MTP1, eager,
M=512-projection-repair, 256-token-profile configuration, except it restores a
device synchronization immediately after each selectively repaired projection.
This is deliberate fault-localization instrumentation. If an asynchronous
projection fault recurs, it should surface at its originating call rather than
at a later allocation.

The complete twelve-prompt strict workload remains mandatory. Cached tokens
must remain zero, all objective canaries must pass, repeat-8 must have one
output class, and every complete token-ID stream must equal deterministic TP2
target baseline D59r. Any new Xe reset, fault, timeout, device loss, OOM, I/O
fault, or output mismatch rejects the arm and stops GPU work.

Because D62 adds synchronization barriers, its speed is diagnostic and cannot
be promoted. A clean pass authorizes exactly one fresh no-barrier MTP1 strict
replay against D59r. It does not authorize deeper MTP by itself.
