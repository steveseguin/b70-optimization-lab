# Packet91 CPU-only orchestration

`orchestrate.py` reads packet91's A grid and B confirmation/full grid, selects the
same exact improving composition, reseals it, runs CPU and chain prechecks, and
writes `ready.json`. It prints a future coordinator command; it never launches.
A pending grid leaves `ready=false`, even when CPU preparation passes.

Run from the repository root:

```sh
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 /home/steve/.venvs/deepseek-v4-xpu/bin/python -B experiments/own-xpu-runtime/ops/packet91-orchestration/orchestrate.py </dev/null
```

`--pin key=value` permits **only** the packet84 baseline default, including
`route=production`, `recurrence=rec-parallel` and `expert_hc=none`. A partial
reversion cannot authorize an unconfirmed combination. `--closed 91=reason`
can close a pending composition only with both route and recurrence explicitly
pinned to default. It cannot override a winner, conflict or failure. The packet90
extension is empty; its default is none. No p81/p82/p83/p84s result is reused as
a matched packet91 screen.

The two inherited temp-directory readiness tests are fixed in **this copy**:
repo paths are stored relatively, external temporary test paths absolutely.
Packet84's running helper and its existing tests remain untouched.

`verify_ready.py` checks the boot, all source/receipt/check hashes, command and
fresh chain destination. `device-entry.sh` is a manual coordinator entry point,
not used during CPU preparation. Do not run it before the coordinator owns
admission and the live packet84 chain is finished.

Test with nice19, the helper CPU mask, stdin `/dev/null`, and
`/home/steve/.venvs/deepseek-v4-xpu/bin/python -B -m pytest -q -p no:cacheprovider test_orchestrate.py`.
