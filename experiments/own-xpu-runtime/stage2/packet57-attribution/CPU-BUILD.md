# Packet 57 lean CPU preparation

Use one compiler at a time, helper CPUs, nice 19 and `python3 -B`. No model
weights, device program, server, service or health probe is executed here.
The new build lives only under
`/home/steve/own-xpu-runtime-results/packet57-attribution/build`.
Input metadata and the packet 49 oracle are read-only links. The compiler
scratch/build cap is 1 GB; only this packet's regenerable objects may be removed.

```bash
P=experiments/own-xpu-runtime/stage2/packet57-attribution
cpu57() {
  nice -n 19 taskset -c 4-15,20-31 env OMP_NUM_THREADS=2 python3 -B "$@"
}
cpu57 "$P/build.py" prepare
cpu57 "$P/build.py" gnu-host --jobs 1
cpu57 "$P/cleanup_objects.py"
cpu57 "$P/build.py" device --jobs 1
cpu57 "$P/cleanup_objects.py"
cpu57 "$P/p57_cpu_gate.py"
cpu57 "$P/p57_window.py" --plan
```

The host gate runs four fresh miniature Engine requests: unchanged packet 56
control, packet 57 token control, and two packet 57 attribution repeats. It
compares target tokens, proposal sequence, hit/miss counts and every retained
layer fixture. The header-only recorder test verifies sample boundaries,
site classes and event guards. Admission tests check parent source/receipt
identity and ensure planning never launches. Failed scratch is retained;
passed scratch is reduced to a compact hash-bound gate receipt. These checks
are not real-model certification and do not substitute for coordinator KD and
WS oracle gates.

After the reviewed code commit is pushed, put its commit ID into
`runtime-revision.json`, then create and verify the final seal:

```bash
cpu57 "$P/p57_seal.py"
cpu57 "$P/p57_seal.py" --verify
```

Never overwrite a seal or reseal a started chain. Inherited packet 56 operator
evidence is explicitly labeled, while all packet 57 compiler inputs, binaries,
CPU gates, coordinator helpers, oracle scripts and observation configuration
are bound by the new seal. The full-mode historical helpers copied with the
source are not alternative launch instructions; use only [WINDOW.md](WINDOW.md).
