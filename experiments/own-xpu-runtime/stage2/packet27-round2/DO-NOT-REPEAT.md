# Packet 27: do not repeat

| Closed mistake or excluded design | Evidence | Revisit condition |
| --- | --- | --- |
| Compare GEMV candidates with the slow diagnostic “current” kernel | Packet25 G1 receipt; packet26 K2 aliased GEMV columns | Always measure runtime R5 and each named alternative in one K2 owner. |
| Use packet18 as the performance incumbent | Packet26 measured selection is 17.85 tok/s in its coordinator receipt | Packet27 defaults and K2 references preserve that selection. |
| Select a candidate without every workload beating the incumbent by 10% | `k2_summary.py`, `test_window.py` | No exception; identical submission bodies never qualify. |
| Advance the pool fixture position without constructing coherent retained pool history | `fixture_driver.cpp`, position63 regression | Historical completed pools must agree with raw history; current pool remains candidate-computed. |
| Require nice19 inside a wrapper that requested nice0 | `priority-gates.json` | Native priority is explicit, checked and receipted. |
| Move sibling GEMVs before their input exists, across a data writer, or across card ownership | `main.cpp`, `review-small-gemv.md` | Exact tuple plus dependency/ownership guards; active/error metadata is not the dense input vector. |
| Generic device descriptor interpreter | Packet24 card receipt, independent reviews here | Compile-time tuples and operation-specific bodies only. |
| Decode all weights to a temporary array then GEMV; R6 register/SLM/pipeline decoders | Packet25 and packet11 negative records | Excluded; input BF16-to-FP32 preparation is a separate exact mechanism. |
| Validate CPU arithmetic but skip native argument checks | `validation_mirror.py`, `validation-gates.json` | Verbatim packet8/9/10 and non-GEMV checks, real K2 extents, poison controls. |
| Omit precise math options at link | Packet17 device incident | Compile and link flags are both sealed. |
| Predict the small-kernel target solely from launch count | `small-gemv.md` | These tuples are a 2–3 ms hypothesis; reaching 11→5 ms still needs measured new work. |

No device ran for packet27 preparation. No candidate is admitted yet.
