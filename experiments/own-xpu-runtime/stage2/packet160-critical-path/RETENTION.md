# Packet160 retention review

`evidence/scoped-intervals.csv.gz` is **1,297,878 bytes**, exceeding the 1 MiB
repository review threshold. Retain it: it contains all 3,780 actual intervals
from packet154's five views, with per-rank exclusive host subsegments at full
stored numerical precision, hit/miss identity, D/R/C/A/B/offset/G and the actual
suffix-wait window. A rounded table, only controls, or a few chosen intervals
would lose the reviewable per-interval evidence requested for this study.
It is gzip-compressed with mtime 0 for deterministic replay, not a generated
cache, model payload or compiled artifact.

Restore/regenerate it from the repository root with:

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet160-critical-path/scopes.py </dev/null
```

The default mode writes only packet160's table/report. `--check` recomputes and
compares every output byte without writing. The complete source dependency
closure is in `evidence/scope-report.json:input_pins`: packet136's committed
record archive, packet126's pure method and packet156's committed compressed
original packet154 streams. Every compressed and decompressed source hash is
checked before use. No access to original local untracked run directories,
model files, GPU, runtime or service is needed to reproduce the scope table.

`evidence/record-intervals.csv` is 417,454 bytes and retains all 1,188 record
intervals, including signed accounting gaps. `evidence/packet149-bracket-summary.json.gz`
is 5,551 bytes; its original 46,787-byte summary was not tracked, so its exact
bytes are retained here with the original and compressed hashes in
`evidence/packet149-retention.json`. This is necessary for the 96-exchange
cost/census replay after cleanup of that older run.

All other outputs are small source, notes, hashes, reports or tests. Final
`evidence/validation.json` records total retained bytes and the largest file.
No existing evidence was removed, archived or consolidated. No build or
device-stage writes are planned; the 27 GB CPU stop and 25 GB device floor labels
do not authorize a device launch.
