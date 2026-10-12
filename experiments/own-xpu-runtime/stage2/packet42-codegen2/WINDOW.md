# One-card coordinator window: repaired after failed K0

Run these from the repository root only after the coordinator admits card 2.
No command below was executed by this CPU-only preparation. `--scope` puts each
long window in its own systemd user unit while inheriting the coordinator's
CPU affinity and environment. LD_LIBRARY_PATH is forwarded unchanged, including
its absence; system library directories are not required inside that variable.
Use a fresh output directory and fresh unit name for each separately authorized
attempt. No automatic retries.

Set the admitted card and packet path in the coordinator's shell:

```bash
P42=experiments/own-xpu-runtime/stage2/packet42-codegen2
CARD=2
```

The October 12 K0 failed before compilation because floor submitted empty
bindings. Tiny shared that helper. The failed files and superseded seal are in
[evidence/20261012-k0-empty-bindings](evidence/20261012-k0-empty-bindings/README.md).
No fault latch was found. Do not reuse the old output names.

The sealed [real-owner CPU binding gate](binding-gates.json) must pass before
admission. Its host-only builds traverse all six actual main functions and the
full native argument/binding paths; it does not compile device bundles or run
kernel arithmetic. Device K0 and on-card output gates remain required.

K0 compiles all images of the exact benchmark executables, using their
compile-smoke modes. It does not submit kernels.

```bash
nice -n 19 ionice -c 3 systemd-run --user --scope --unit=packet42-k0b -- \
  nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B "$P42/window.py" \
  --authorized-device-window --window K0 --card 2 --output "$P42/build/k0b"
```

T1 measures the launch floor: 1,176 matrix rows and four 1,000-launch burst rows,
200 repetitions each, then writes launch-table.md and its measured shape rule.

```bash
nice -n 19 ionice -c 3 systemd-run --user --scope --unit=packet42-t1b -- \
  nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B "$P42/window.py" \
  --authorized-device-window --window T1 --card 2 --output "$P42/build/t1b" \
  --k0 "$P42/build/k0b/window.json"
```

K2 measures candidates against their actual runtime incumbents, retaining failed
cases as rows. It writes table.md sorted by measured ms/token saved and
`dispatch-measured.json` in the packet26 vocabulary.

```bash
nice -n 19 ionice -c 3 systemd-run --user --scope --unit=packet42-k2b -- \
  nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B "$P42/window.py" \
  --authorized-device-window --window K2 --card 2 --output "$P42/build/k2b" \
  --k0 "$P42/build/k0b/window.json" --t1 "$P42/build/t1b/window.json"
```

K0/T1 identity must match card, boot, native hashes and relevant environment.
The wrapper checks all libraries before device contact, then records its own
kernel journal cursor. A historical fault line cannot latch this window.
Storage/format/loader failures report a failed window without a fault latch.
Read [DEADLINES.md](DEADLINES.md) for reporting estimates, watchdogs and graceful
stop rules. No device or driver recovery is authorized by these commands.

The binaries, exact hashes, source pins and component argument lists are sealed
in [build-receipt.json](build-receipt.json). Local build artifacts are ignored;
CPU build scripts and compressed assembly are retained in this directory.
