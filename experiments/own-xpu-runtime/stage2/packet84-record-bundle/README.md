# Packet84 record bundle 2

Copied from frozen packet80; target arithmetic remains iq3-p49-split32-v1 and
packet49 remains the oracle. No GPU, service, or chain is launched by preparation.

Baseline from the coordinator brief: ordered host cleanup, hc-wide, production
route/norm/dense, wide64 experts, draft-HC, batch rollback, rank1 at 24/24.
Packet81 experts, packet82 recurrence and packet83 draft heads are independent
choices. Packet80's four placements remain available with the production draft
head. Packet83 draft heads are admitted only at placement1, as preregistered.
Q4 plus a smaller prefix is excluded. Full BF16 KV and the full target head stay
unchanged; Q4 and smaller prefixes alter draft proposals only.

Preparation is in progress. GNU-host and Intel-device binaries built serially;
the device binary has not been executed. CPU validation and seals must pass
before any readiness claim. See [orchestration](../../ops/packet84-orchestration/README.md).

The expensive proof is cached independently of coordinator options. Selected
composition seals are materialized on demand; changing --pin requires no merge
or compile. ready.json requires completed source screens and selected prechecks;
it never launches its recorded command.
