# Packet28 negative index

| Arm | Evidence and disposition | Revisit condition |
|---|---|---|
| 64-bit code words in the weight loop | Clean bounding study found wide loads/shifts slower; new byte grids avoid them | New same-card matched evidence, not instruction-count inference |
| scale or exceptional test per weight | Expanded scale-byte reconstruction repeats per weight; IQ packed scaled-NaN test repeats per weight. Dense Q6/Q8 had no IQ exception test. Hoist invariant work safely | A tile actually crosses a group, or exceptional fallback requires original spelling |
| packet25 harness current as runtime reference | Its current was about2.5× actual R5; cannot establish runtime gains | Use packet26 actual entry/overlay and reproduce in-model time within15% |
| claimed universal NaN payload identity from source algebra | Both compilers expose payload choices on mixed NaNs; CPU receipts count them | Same-card strict byte gates plus unchanged arithmetic oracle, no canonicalisation |
| use launch count as speed | WG32 split4 adds a final event while keeping arithmetic | Compare summed event times then full-model wall time |
