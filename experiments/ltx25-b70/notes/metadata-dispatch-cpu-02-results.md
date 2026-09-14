# CPU metadata attribution: repeated traversal is measurable

September 14, 2026. Corrected CPU fixture passed exact registered-state-name
comparison against the frozen native checkpoint census. It uses video FF biases
disabled and audio FF biases enabled, matching all 84 state names per block.
Module-name expectations derive from those names and the pinned constructors'
eight parameterless dropout paths; native receipts do not contain a module tree.
[Initial rejected fixture](metadata-dispatch-cpu-01.md) remains preserved.

The test uses the native 48-block class/registration, split21 ownership and
adjacent-state adapter79b4. CPU-only 32-wide BF16 states replace full checkpoint
weights; two stage-shaped argument trees use an identity compute spy. The
simulated node gate retains the third validation boundary. No native block
forward or compiler execution occurs; no tensor numerical values are used.

A separate count pass verified **1,584 state and 1,584 registry validations**
for 528 block calls. After removing counting wrappers and one warmup, three
uninstrumented wall samples were **0.479976, 0.479732 and 0.479624 seconds**,
median **0.479732 s**. CPU time was nearly identical. Native pre_run, setup and
output writes are outside this explicitly route-only timer.

One separate cProfile pass took 1.558 seconds because profiling adds overhead.
It attributed much work to repeated native `parameters`, `buffers`,
`_named_members` and `named_modules` traversal. Those cumulative values overlap
and must not be summed or used as uninstrumented measurements. The full native
node's filesystem, JSON, census/counter reporting and actual kernels are absent.
This is a source-backed optimization target, not proof that native generation
will improve by 0.48 seconds or that all compiled overhead has been explained.

XPU stayed uninitialized before/after work; max RSS was802,356 KiB. No device
requests, numerical compilation, application reload or host setting changes.
[Report](../data/metadata-dispatch-cpu-02/result.json),
[separate profile](../data/metadata-dispatch-cpu-02/cprofile-top.txt), and
[fixture correction](../patches/metadata-dispatch-cpu-02/manifest.json).
Full script/adapter snapshots remain under
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/metadata-dispatch-cpu-02`.

```bash
PYTHONDONTWRITEBYTECODE=1 /home/steve/.venvs/ltx25-baseline/bin/python scripts/profile-adjacent-metadata-cpu.py --cpu \
  --output-dir /mnt/fast-ai/bench-results/ltx25-baseline-20260913/metadata-dispatch-cpu-02 \
  --rounds 3
```

Next: a single module traversal can inspect hook state and direct registered
parameters/buffers together, avoiding repeated recursive iteration. Preserve
all three execution boundaries, owner and registry checks, hook rejection,
BF16/device validation and empty-state rejection. Account for shared modules,
aliased tensors and None registrations; do not cache state across calls. First
validate exact acceptance/rejection and CPU cost before another native build.
