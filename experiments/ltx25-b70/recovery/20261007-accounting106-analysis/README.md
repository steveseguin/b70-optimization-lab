# Packet106 posthoc counter analysis

This standalone CPU reader preserves `diagnostic_valid=false`. Packet106's
accounting run contains two incomplete snapshots and is not a valid whole-run
diagnostic. A surviving subset is explicitly posthoc and exploratory. No output
artifact is created unless `--out PATH` is specified; that path must not exist.

```sh
python3 -B analyze.py
python3 -B -m unittest -q test_analyze.py
```

Inputs are fixed to packet106: raw accounting, fast proof, campaign result,
manifest, server identity, plan, collector contract, reviewed device mapping,
mapping dependencies, collector/verifier source, and the coordinator's
post-completion recursive proof receipt. This reader verifies their hashes and
identities. It relies on that pinned completed quality proof; it does not rehash
tensors or issue requests. Output also identifies the analyzer's own source.

Admission is derived from data, not an index allowlist. Each collector triple
`(monotonic_start_ns, unix_start_ns, monotonic_end_ns)` supplies an offset bracket.
All observed brackets must have a common intersection. Their outer envelope,
plus the server timestamp's sub-millisecond truncation uncertainty, gives a
conservative inner window between the first and last scored delivery successes.
Both complete endpoint scans must lie strictly inside it. Only adjacent samples
with no intervening record or cadence gap can form a pair. Render ownership,
client identities, engine coverage, capacity/default flags, raw counters, and
watermarks must remain usable; duplicate client observations are conservatively
excluded. Every excluded pair retains its reason.

The raw file currently yields seven adjacent pairs spanning sample indexes5–12.
This is an observed result, not a selection criterion. Output contains separate
per-client CCS/BCS cycle deltas and each engine's own total-cycle delta. It never
converts them into utilization, busy seconds, cross-client/card aggregates, or
sampler phase attribution. Read-time bounds account for non-simultaneous scans.
Clock consistency cannot rule out an unobserved wall-clock step between samples.
The delivery window includes asynchronous lookahead and tails, not exclusively
the work that produced the ten exact scored clips.

The complete diagnostic remains invalid even when interior pairs survive.
Failed collection is not silently repaired, and numerical quality is separately
anchored to the coordinator's sealed-verifier proof.
