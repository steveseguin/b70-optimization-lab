# Packet128 fresh in-engine budget — pending

No packet128 device job has run in this CPU preparation session. No class cost,
wait cost, overhead ratio or projected gain is asserted yet.

The coordinator runs the single proposed lane-B load, then `analyze.py` as shown
in [README.md](README.md). The report requires both ranks, all 48 layers in both
hit/miss populations, all 12 exact 64-token requests, released lane ownership and
matching binary/selection identities. It prints the throughput distortion check
first and withholds rankings below 90% of the historical 58.3 tok/s reference.

The generated report will contain per-rank, per-outcome class milliseconds,
observed same-queue gaps, explicit head waits and native draft waits. Critical-path
opportunities will be labeled as ideal bounds and optimistic scenarios. Host and
device durations will not be added into a fabricated wall-time decomposition.
