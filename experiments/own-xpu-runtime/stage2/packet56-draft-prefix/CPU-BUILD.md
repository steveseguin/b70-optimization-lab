# Packet56 CPU preparation

Run from the repository root. No device executable is invoked during these
steps. Use one compiler at a time; all work stays on helper cores at nice 19.
The build link points only to this packet's external results directory.
Parent metadata/fixtures and the packet49 oracle are read-only links.

```bash
P=experiments/own-xpu-runtime/stage2/packet56-draft-prefix
cpu56() {
  nice -n 19 taskset -c 4-15,20-31 env OMP_NUM_THREADS=2 python3 -B "$@"
}
cpu56 "$P/build.py" prepare
cpu56 "$P/build.py" gnu-host --jobs 1
cpu56 "$P/build.py" device --jobs 1
cpu56 "$P/p56_cpu_gate.py" --build
cpu56 "$P/cleanup_objects.py"
```

The numerical CPU gate uses a synthetic 248,320×2,560 expanded Q6 head and
checks every one of the 91,392 prefix logits byte for byte (182,784 bytes),
plus smaller edge cases. Its backing allocation is shared with the full-head
control. It checks the actual production round2 argmax with deterministic
ties and poisoned suffix values. The unchanged native controller is exercised
with mock rank state: excluded target IDs must cause ordinary misses and the
outputs, committed state and fixtures must equal sequential execution.
Two fresh host processes agree. This is not real-model certification.

Calibration uses the existing tokenizer's `regex` dependency in the lane venv:

```bash
nice -n 19 taskset -c 4-15,20-31 \
  /home/steve/.venvs/vllm-xpu/bin/python3 -B "$P/calibrate.py" --verify
cpu56 -m unittest discover -s "$P" -p test_packet56.py -v
nice -n 19 taskset -c 4-15,20-31 \
  /home/steve/.venvs/vllm-xpu/bin/python3 -B -m pytest \
  "$P/test_submission56.py" -q
```

The final CPU seal binds new compiler inputs/binaries, the prefix CPU gate,
the independent selection and configuration, and the unchanged parent's
target/operator evidence. Parent gate expectations are explicitly inherited;
they are not reported as new packet56 CPU runs. The coordinator repeats the
device/operator and model checks in this packet's chain.

After committing the reviewed implementation, record that commit in
`runtime-revision.json`, then seal and pin the local submission lineage:

```bash
cpu56 "$P/p56_seal.py"
cpu56 "$P/p56_seal.py" --verify
cpu56 "$P/packet56_submission.py" --help
```

The sealer writes the local submission pin. Never overwrite a final seal or
reseal after a device chain starts. Fresh output paths and a new reviewed
packet are required for changes. Retain build logs and byte-test receipts;
only this packet's regenerable objects may be cleaned. Peak build cap: 1.5 GB.
