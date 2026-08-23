# Ornith 1.5 35B-A3B: paired alpha/beta projection is blocked by buffer aliasing

Date: 2026-08-23 EDT

Status: **CLOSED STRUCTURAL NEGATIVE — do not enable or ship**

Ornith's Qwen-derived recurrent layers expose a plausible launch-reduction
transfer: every recurrent layer applies adjacent Q4_K `[2048,32]` alpha and
beta projections to the same normalized activation. A default-off ESIMD
candidate submitted both exact two-row reordered DMMVs as one kernel, which
would remove 30 launches per generated token.

The strict graph matcher did not activate. Bounded live-graph diagnostics
showed that the intended nodes otherwise match completely: alpha and beta are
six graph nodes apart, use the same activation object, are contiguous and
unsplit, each has one consumer, and both qualify for the incumbent reordered
DMMV path. The decisive observation was `beta->data == alpha->data`.

That equality is intentional memory-planner reuse. In the ordinary graph,
alpha is consumed before beta is produced, so their lifetimes do not overlap.
A paired kernel launched at alpha would write beta into the same allocation and
overwrite alpha before alpha's add/softplus/gate consumers run. The candidate's
alias guard therefore prevented corruption. The door-on transcript remained
canonical only because fused hits were zero; this is not a candidate
correctness or speed result.

Making this fusion valid would require a graph/lifetime change or a separate
beta allocation, whose memory and scheduler consequences exceed the scope of a
narrow backend fusion. No matcher condition was weakened and no timing was
performed. The accepted seven-fusion stack was restored byte-for-byte.

The complete experimental source is preserved at
`../patches/llamacpp-ornith15-alpha-beta-paired-buffer-alias-negative-20260823.patch`.
The structured diagnostic record is under
`../data/2026-08-23-ornith35b-alpha-beta-paired-buffer-alias-negative.json`.
