# Source observations after the combined result

This is a source-only map for later selection, not a third kernel experiment.
Finish the narrow lossless state-bundle qualification first. The earlier class
profile belongs to the original binary; no new per-format profile is asserted.

Gate and up experts have identical format/shape at every one of48 layers:
20 IQ2_S,17 IQ3_XXS,10 IQ3_S and1 IQ4_XS, each [512,640,2560]. Their original
aggregate class times total17.25% of summed whole-request GPU event duration.
That total cannot be assigned to one format or treated as a predicted fusion
benefit. The two classes currently run separately in the unfused GSQ graph.
A later paired projection candidate would need to preserve each independent
accumulation/reduction and all intermediate BF16 outputs; shared inputs alone
do not establish a worthwhile speedup. Whole-model expert expansion would add
substantial storage and is not admitted by these observations.

GDN-Z has14 Q6_K,10 Q4_K,8 IQ4_XS and4 Q5_K sites, each [6144,2560]. The proven
Q6/K2560 operator can support reuse of unchanged arithmetic evidence if that
path is selected later. Its original7.80% aggregate spans all four formats;
the14 Q6 sites are not a measured7.80% opportunity. Avoid a redundant exhaustive
proof/micro campaign merely for another row count.

Expert down has39 IQ4_NL and9 Q2_0 sites, each [512,2560,640]. Keep route and
per-slot input semantics explicit in any future candidate. The observed full
combined run is now the internal exact candidate; use actual evidence to choose
the next worthwhile delta after capture friction is reduced.

[Exact metadata counts and authority](next-source-census.json) preserve these
observations. No weights were read, code changed, model run or speed predicted.
