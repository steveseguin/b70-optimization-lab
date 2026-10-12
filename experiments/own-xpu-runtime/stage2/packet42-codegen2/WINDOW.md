# One-card coordinator window: prepared, not run

Run these from the repository root only after the coordinator admits card N.
No command below was executed by this CPU-only preparation. `--scope` puts each
long window in its own systemd user unit while inheriting the coordinator's
CPU affinity and environment. LD_LIBRARY_PATH is forwarded unchanged, including
its absence; system library directories are not required inside that variable.
Use a fresh output directory and fresh unit name for each separately authorized
attempt. No automatic retries.

Set the admitted card and packet path in the coordinator's shell:

```bash
P42=experiments/own-xpu-runtime/stage2/packet42-codegen2
CARD=N
```

K0 compiles all images of the exact benchmark executables, using their
compile-smoke modes. It does not submit kernels.

```bash
nice -n 19 ionice -c 3 systemd-run --user --scope --unit=packet42-k0 -- \
  nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B "$P42/window.py" \
  --authorized-device-window --window K0 --card "$CARD" --output "$P42/build/k0"
```

T1 measures the launch floor: 1,176 matrix rows and four 1,000-launch burst rows,
200 repetitions each, then writes launch-table.md and its measured shape rule.

```bash
nice -n 19 ionice -c 3 systemd-run --user --scope --unit=packet42-t1 -- \
  nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B "$P42/window.py" \
  --authorized-device-window --window T1 --card "$CARD" --output "$P42/build/t1" \
  --k0 "$P42/build/k0/window.json"
```

K2 measures candidates against their actual runtime incumbents, retaining failed
cases as rows. It writes table.md sorted by measured ms/token saved and
`dispatch-measured.json` in the packet26 vocabulary.

```bash
nice -n 19 ionice -c 3 systemd-run --user --scope --unit=packet42-k2 -- \
  nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B "$P42/window.py" \
  --authorized-device-window --window K2 --card "$CARD" --output "$P42/build/k2" \
  --k0 "$P42/build/k0/window.json" --t1 "$P42/build/t1/window.json"
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
