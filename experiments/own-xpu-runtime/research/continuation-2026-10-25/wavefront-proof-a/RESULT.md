# Four-stage forced-miss state proof: PASSED

This is a scripted proposal and rollback diagnostic, not live drafting or a speed result.
The run used boundaries [0, 13, 25, 37, 48], 87 prompt tokens,
and 32 outputs. Native terminal cleanliness: True.

The 6 forced positions were [87, 95, 96, 97, 111, 117].
Every requested rejection and rollback was observed: True.
Per-stage abort counts: [6, 5, 2, 0]; byte-verified restores:
[6, 5, 2, 0].

Output tokens match the retained PP2 target-only baseline: True.
Strict canonical state/layout comparison passed: True across
2065 buffers. Comparison checks every canonical buffer,
sealed native wavefront quiescence, restored-state counters and committed position.
The two engine identities are recorded separately in [summary.json](summary.json);
the derived manifests share only model, tokens, arithmetic and position identity.
Pinned historical manifests remain unchanged.

Full comparison: [comparison.json.gz](comparison.json.gz). All native stage metadata,
state seals/indexes, terminal result and schedule are retained alongside it.
Raw state payloads total 417,299,400 bytes and remain at their original
external paths with hashes; a durable archive is pending. Do not remove originals.
No diagnostic throughput is promoted to a performance claim.
