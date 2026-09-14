# One-pass state traversal04: CPU regression pass and lower metadata cost

September 14, 2026. The inactive [candidate](../patches/multiblock-onepass-state-04/README.md)
uses one module traversal to inspect local hooks and directly registered
parameters/buffers. Class, route, owner, global hooks, BF16/device and nonempty
state checks remain. Each of the same three lifecycle boundaries performs fresh
checks; no cache or tensor arithmetic is introduced. Different simultaneous
violations can change first-error order. Native GPU qualification is pending.

The existing [60 CPU lifecycle checks](../data/onepass-state-cpu-01/lifecycle.json)
all passed against source SHA256
`ba89394822e9ec607cc8ec7aad092a3afa7d87e0f723b781cf27f1f6158c031b`.
The regression preserved three state and registry checks per invocation,
including late changes after routing and at the native gate. This existing
suite is not the complete new alias/None-registration edge-case suite.

The same corrected84-state/73-module CPU fixture, with only adapter source/pin
changed, measured **0.313064, 0.313355 and 0.313056 seconds** for528 fake-compute
route calls. Median0.313064s versus the parent's0.479732s in its earlier separate
process is about0.167s or35% less metadata/dispatch time. These are three-sample
CPU measurements, not an interleaved same-process causal estimate or a video
speed result. Both count gates observe1,584 state and1,584 registry checks.
XPU stayed uninitialized; actual compiler and native block forward never ran.

[CPU cost report](../data/metadata-dispatch-cpu-03-onepass/result.json),
[profile](../data/metadata-dispatch-cpu-03-onepass/cprofile-top.txt),
[parent attribution](metadata-dispatch-cpu-02-results.md).
The new `profile-onepass-metadata-cpu.py` differs from the frozen parent harness
only in the adapter path and SHA. Full source snapshots remain in the local
`metadata-dispatch-cpu-03-onepass` and `onepass-state-cpu-01` evidence directories.

Commands from this lane:

```bash
/home/steve/.venvs/ltx25-baseline/bin/python scripts/test-adjacent-state-reuse-cpu.py \
  --adapter patches/multiblock-onepass-state-04/candidate.py \
  --adapter-sha256 ba89394822e9ec607cc8ec7aad092a3afa7d87e0f723b781cf27f1f6158c031b \
  --expected-state-scans 3 \
  --output /mnt/fast-ai/bench-results/ltx25-baseline-20260913/onepass-state-cpu-01.json \
  --evidence /mnt/fast-ai/bench-results/ltx25-baseline-20260913/onepass-state-cpu-01
PYTHONDONTWRITEBYTECODE=1 /home/steve/.venvs/ltx25-baseline/bin/python scripts/profile-onepass-metadata-cpu.py --cpu \
  --output-dir /mnt/fast-ai/bench-results/ltx25-baseline-20260913/metadata-dispatch-cpu-03-onepass \
  --rounds 3
```

Next: focused shared-module/tensor-alias/None-registration acceptance and
rejection checks, then a sealed native candidate comparison. Consider compact
receipt writing only as a separately identified delta with its own acceptance
checks. Do not attribute CPU savings to native generation or restart for the
small serializer change alone. Packet07/PID56711 remains unchanged, healthy
and idle on restored original dispatch; the full real-time goal remains active.
