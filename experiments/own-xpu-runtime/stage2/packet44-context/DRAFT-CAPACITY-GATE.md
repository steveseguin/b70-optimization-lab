# CPU draft references at each capacity

`capacity_draft_gate.py` is prepared but has not been executed by its author.
It never runs device binaries. Run it only after both packet44 host builds and
the required input bundle are complete, with no concurrent host-model gate:

```sh
nice -n 19 ionice -c 3 python3 -B experiments/own-xpu-runtime/stage2/packet44-context/capacity_draft_gate.py --run
```

`--prepare-only` verifies and copies the input prefix without executing a host
binary. Exactly one of `--prepare-only` or `--run` is required. Both variants
write only packet44. A nonblocking packet-local lock prevents overlapping draft
runs. Existing output directories cause refusal, not an automatic retry.

The immutable packet38 source has 150 confirmed stream files and 151 target
rows, bound to its retained `capture-input-incident-retrospective.json`.
The script verifies every source stream hash, the table hash and the target-row
hash. It copies only 94 streams (87 prompt tokens + 8 generated prefix tokens −
1), plus 95 target rows. Each TSV row uses the **next row's input token**, as the
original capture code does. Head execution begins at position 85, preserving
the last-prompt-boundary behavior (nine head rows). Paths in the new table point
only into packet44. `capture-input-incident-retrospective.json` records new
input hashes and the complete source provenance.

Run order is GNU then icpx at 256, followed by GNU/icpx at 4,096 and 32,768.
Every arm uses `dispatch-p38.json`, the packet44 input bundle and two OMP
threads. Before execution the script refuses accelerator-linked ELF binaries.
One child runs at a time, inherits the current affinity and receives nice 19
and idle I/O scheduling. The script monitors its own plus child anonymous
memory against 8,000,000,000 bytes, applies a two-hour CPU-arm bound, polls
storage throughout, checks `df -B1 /` before large writes, preserves the 8 GB
root floor and enforces the agent's stricter 4 GB packet build ceiling.

GNU fixtures remain in `build/draft-reference-c{capacity}` for coordinator KD.
They are bound by `capture-run-incident-retrospective-c{capacity}.json`, which
contains the executed binary hash, table hash and every fixture hash. icpx
fixtures must match every GNU file hash at the same capacity. All retained
per-row valid-prefix fixture hashes must also match across capacities. The
full final cache is compared between compilers at the same capacity; its unused
allocation tails differ in length across capacities. Each comparison receipt
lands before duplicate icpx scratch is archived and deleted. Logs are hashed,
compressed, round-trip verified and removed immediately after each arm.

The final `capacity-draft-gates.json` supplies
`draft_capture_fixture_sha256_by_context` and `draft_capture_input_sha256` for
the build receipt. It requires six successful arms and less than 300 MB total
retained GNU reference bytes. These are CPU reference gates, not device results
or speed measurements.
