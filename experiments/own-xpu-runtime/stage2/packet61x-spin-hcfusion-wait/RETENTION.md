# Packet61x retention and CPU reproduction

The ignored build retains 108,164,001 logical bytes. Unchanged objects are
hardlinks to packet61; parent operator fixtures and inputs are read-only
symlinks. The kernel bundle embedded in the device executable is byte-identical
to packet61: 5,355,244 bytes, SHA256
`14e449bbcefbf8e076c8ddcb2c477460117b6db3a6075361e44b46c4e8b41afe`.
[Direct ELF comparison](evidence/kernel-bundle-identity.json) and
[71 inherited object checks](evidence/object-identity.json) retain the proof.
No model payload was copied or read.

Retain both engine binaries, test binaries, generated checked headers,
compiler/link objects, commands and CPU fixture outputs. The build receipt
binds actual inputs and objects, including the parent's checked source closure.
The fixture and chain bind this packet's new source closure. Do not write
through inherited hardlinks or symlinks. Retain packet61's and packet56x's
sealed parents and all their build dependencies.

For a fresh, unsealed reproduction with those parents restored, copy this
packet's sources and retained fixture inputs, then run:

```bash
P=experiments/own-xpu-runtime/stage2/packet61x-spin-hcfusion-wait
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 python3 -B "$P/build_engine.py"
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 python3 -B "$P/cpu_gate.py"
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/seal_and_plan.py"
```

These entry points refuse an existing seal. Do not delete seals to rebuild an
admitted candidate. Ignored build files are reproducible local inputs, not
public release assets. The primitive fixture and primitive receipt are
retained parent evidence; the final parent build receipt supplies the checked
source identity. Historical helper/CMake files are not this build recipe.

The 33 chain/submission tests used the existing
`/home/steve/.venvs/vllm-xpu/bin/python3 -B -m pytest -q -p no:cacheprovider`
with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, `PYTHONDONTWRITEBYTECODE=1`,
`OMP_NUM_THREADS=2`, nice19 and helper affinity. The system Python has no pytest;
no package or environment was installed or changed.
