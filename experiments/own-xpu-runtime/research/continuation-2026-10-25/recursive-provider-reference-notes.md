# Recursive provider reference provenance

Use [recursive-provider-reference-v2.json](recursive-provider-reference-v2.json)
for qualification. It is the reproducible output of
[build_recursive_provider_reference.py](build_recursive_provider_reference.py).
The earlier [recursive-provider-reference.json](recursive-provider-reference.json)
is retained as the initial manually assembled join, not the launch authority.

Both packets contain the same 117 canonical true pairs and the same 32 actual
recursive d1/d2 predictions at seed positions 86–117. Version 2 adds the builder
identity, explicit per-row depth-two eligibility, and absolute source paths;
it does not replace or correct any predicted token. Source SHA256 identities
and the accepted canonical draft-state identity are unchanged.

The predictions come from actual discarded, verified depth-three probes joined
to canonical live replay by confirmed seed position/token, raw-hidden hash and
d1 prediction. They were not inferred from consecutive depth-one hits. The
historical probe checked 27,410,742 device bytes, not both pinned allocations.
The new gate separately requires all 73 canonical draft allocations and host
state to match accepted live PP4 after recursive restoration. The first gate
keeps target owners quiescent and discards proposals; this reference does not
qualify target consumption, overlap, speed or independent CPU arithmetic.
