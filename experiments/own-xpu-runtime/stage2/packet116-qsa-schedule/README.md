# Packet116 — exact QSA scheduling

CPU-only preparation of an exact schedule for the current
`iq3-p49-split32-v1` model. [Audit](AUDIT.md),
[work note](../../../../notes/2026-10-18-own-runtime-packet116.md).

The micro kill gate is combined `qsa.attention` + `qsa.select` time at
context128 no greater than0.6× production in each of two fresh processes.
Both execution orders and context4096 are also measured. Every class event
is summed per invocation. No v5 run is eligible until both processes pass
full state equality and the kill gate. GPU measurements are coordinator work.

`p116_qsa_host.hpp` independently visits the exact tree; `p116_qsa_kernel.hpp`
implements the device schedule; `p116_qsa_submit.cpp` binds the existing
allocation/scratch layout. `cpu_gate.py` compiles and runs two processes under
each of GNU and Intel. `micro/` contains the complete-layer comparison and
proposed coordinator job. `v5/` contains the prepared one-load bracket.
