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

GNU-host and Intel-device binaries built serially; the device binary has not
been executed. The 768-composition byte matrix, 2,688 per-card post-load
censuses, 223 miniature runs and CPU admission gates passed. Q4 adds
146,227,200 bytes on rank 1 and leaves 798,864,694 bytes of arena headroom.
The baseline selected rehearsal passed in 28.9 seconds; source-screen
confirmations and a fresh device chain remain pending. See [orchestration](../../ops/packet84-orchestration/README.md).

The expensive proof is cached independently of coordinator options. Selected
composition seals are materialized on demand; changing --pin requires no merge
or compile. ready.json requires completed source screens and selected prechecks;
it never launches its recorded command.

## CPU proof and fast selection

The matrix contains 768 choice combinations and 1,344 admitted configurations.
The full-shape test constructs both ranks for every configuration, retaining
actual post-load allocations and operation types with a mock backend. It does
not allocate device memory or read model payloads. Byte proof factors the
independent dispatch sites: GNU and Intel each run the selected operators twice.
Recurrence matches its same-compiler production reference, including NaN bytes;
cross-compiler production NaN differences are not hidden. Q4 matches an
independent scalar Q4 reference, not the original Q6 draft arithmetic.

The cached stage runs once after building. See [retention](RETENTION.md) for the
build and gate sequence. After those gates finish:

```sh
# Prefix every command with nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2.
# Run in this directory, with stdin redirected from /dev/null.
python3 -B prepare_packet.py
python3 -B fast_reseal.py --host ordered --hc hc-wide
python3 -B dry_run.py --cached
python3 -B dry_run.py
```

`dry_run.py` verifies cached source and evidence hashes, imports the pinned
wrapper, exercises the real admission implementation in isolated test roots,
checks K2 post-processing, dispatch merging and submission consumers, then plans
all eleven windows and both screen lanes. It does not acquire live lane leases.
Selected checks must finish within five minutes; resealing must finish within
two minutes. Neither step compiles. `selection_rehearsal.py` switches through
all new draft choices and inherited placements, checks every window plan, and
restores the coordinator baseline while proving cached proof and binaries stayed
unchanged. Candidate arithmetic is never selected for a real chain without the
source screen confirmations and the coordinator's readiness checks.

The readiness reader and all preparation commands are CPU only. Device parity,
acceptance and performance remain the responsibility of a fresh record chain.

See the [CPU preparation closeout](CPU-PREPARATION-CLOSEOUT.md) for retained
evidence and the exact limits of these checks.
