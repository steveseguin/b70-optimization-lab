# Packet 27 CPU preparation closeout

Question: can specialised second-round kernels close part of packet26's measured
55.4 ms/token gap without changing arithmetic identity `iq3-p17-detmath-v2`?
The copied source and original hashes are recorded in `source-proof.json`.
The default is packet26's measured selection, including its R5 GEMVs.

This packet prepares explicit compile-time sibling GEMV tuples, subgroup GDN,
parallel route/rank/argmax and QSA candidates, the real R5 GEMV census, and exact
input-conversion/packed-load/short-row alternatives. Design and arithmetic
arguments are in `README.md` and the three class-specific notes.

Useful repairs: coherent pool fixture history; declared native priority;
per-workload and per-candidate timing admission; continuation after candidate
failures; actual native argument validation on CPU including packed F32; preserved
folded-route dispatch; dependency guards on moved sibling projections.

Independent reviews cover bit identity, write races and interpreter exclusion in
`review-nongemv.md`, `review-gemv.md` and `review-small-gemv.md`. Their findings and
fixes are retained. Native compilation is evidence of buildability only.

Final gate results and executable hashes are in `build-receipt.json` and
`cpu-tests.json`. Device exactness, measured dispatch selection and whole-model
speed remain pending the coordinator's K0/K1a/K1b/K2/W0/W2/W2m/W2c windows.
No device binary ran here and no new speed is claimed.

Revisit each candidate only with its sealed K1/K2 receipt. Preserve the packet26
incumbent when a candidate is inexact, aliases it, or fails the 0.9× median gate.
The small-GEMV target remains a hypothesis; these schedule-legal groups alone
are not evidence of 11 ms becoming 5 ms. See `DO-NOT-REPEAT.md`.
