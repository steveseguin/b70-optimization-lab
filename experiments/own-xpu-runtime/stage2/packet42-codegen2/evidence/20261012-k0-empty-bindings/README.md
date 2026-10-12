# Failed K0: empty compute bindings

Coordinator run on card 2, 2026-10-12 14:25:36 UTC. Floor exited within one
second: `FAILED WINDOW: native infrastructure failed: floor: exit 1: empty compute bindings`.
The shared CompileSmoke helper (floor and tiny) called Device::compute with an
empty allocation list. The owner rejected it before bundle compilation or its
barrier submission. The other four programs used the bundle-only helper.
No kernel fault was reported. T1 and K2 refused because K0 had not passed.

Original build/k0 files and the superseded seal and binary hashes are retained
byte for byte here. No fault latch was found in build/: [].
No GPU recovery or device execution was performed by the repair. The replacement
attempt names are k0b, t1b and k2b.
