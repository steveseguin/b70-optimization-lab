# Packet62 coordinator screens

CPU preparation never starts these device commands. Run only inside the
coordinator's admitted nice-0 user unit, after the chosen cards are available,
with its approved `LD_LIBRARY_PATH` and actual `FAULT_REVIEW` receipt. Lane A
uses physical cards 0+1; lane B uses 2+3. Both native ranks receive card indices
0+1 through the wrapper's device mask. Do not interfere with packet61's record
chain or packet61x, and do not reuse an output directory.

The recommended first comparison is `control` then `batch`, matched within
one lane. The other selections separately expose capture banking and restore
bookkeeping overlap; a faster screen remains nonqualifying.

From the repository root, these functions give the exact common command:

```bash
P=experiments/own-xpu-runtime/stage2/packet62-miss-path
S=experiments/own-xpu-runtime/stage2/screen/v3
screen_a() {
  taskset -c 0-3,16-19 env -i \
    PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
    python3 -B "$S/screen.py" --profile tp2 --lane A \
    --lineage "$P/selections/$1" --seal "$P/selections/$1/screen-seal.json" \
    --authorized-device-window --fault-review "$FAULT_REVIEW" \
    --output "$S/evidence/packet62-$1-A"
}
screen_b() {
  taskset -c 4-7,20-23 env -i \
    PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
    python3 -B "$S/screen.py" --profile tp2 --lane B \
    --lineage "$P/selections/$1" --seal "$P/selections/$1/screen-seal.json" \
    --authorized-device-window --fault-review "$FAULT_REVIEW" \
    --output "$S/evidence/packet62-$1-B"
}
```

Choose the single command matching the admitted window, not the entire table:

| Selection | Lane A command | Lane B command | Pre-device miss-saving expectation |
| --- | --- | --- | --- |
| control | `screen_a control` | `screen_b control` | Zero; matched packet61 behavior |
| batch | `screen_a batch` | `screen_b batch` | Less than the full 0.74 ms rollback envelope; point estimate unavailable |
| banks | `screen_a banks` | `screen_b banks` | Near zero exposed saving expected; capture sits behind rank1 and redo already skipped these restores |
| banks-batch | `screen_a banks-batch` | `screen_b banks-batch` | Restore saving from batch, plus capture saving only if exposed |
| banks-batch-overlap | `screen_a banks-batch-overlap` | `screen_b banks-batch-overlap` | Same, plus unmeasured host bookkeeping overlap; not the 12.51 ms corrected half |

For batch and combined modes, 0.74 ms is an optimistic ceiling assuming the
entire old rollback vanished, not a predicted gain. Some rollback guards,
metadata and all corrected-half work remain. There is no measured packet62
throughput or miss latency yet.

The CPU-only plans, already exercised for every selection and lane, use:

```bash
for choice in control batch banks banks-batch banks-batch-overlap; do
  for lane in A B; do
    nice -n 19 taskset -c 8-15,24-31 python3 -B "$S/screen.py" \
      --profile tp2 --lane "$lane" \
      --lineage "$P/selections/$choice" \
      --seal "$P/selections/$choice/screen-seal.json" --plan \
      --output "$S/evidence/packet62-$choice-$lane"
  done
done
```

Plans do not reserve devices, review faults, write to the shared screen tree or
launch a worker. Retained outputs are `selections/<choice>/plan-A.json` and
`plan-B.json`. A device screen must pass all 13 requests against packet49,
including every generated target token, before considering a full record chain.
