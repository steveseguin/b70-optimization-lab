# Native multiblock screen01: exact outputs, no speed win

September 14, 2026. All 32 clips passed byte-for-byte comparison against the
four original outputs: images, video latent, audio latent and waveform. The
12 compiled clips covered single24, boundary4 and all48, with boat seed42,
marble seed17 and bird seed123. Each selection ran a cold boat qualification
and one restored/compiled/restored triple per scene.

| Compiled selection | Median preview penalty | Median raw archive penalty | Median sampler interval penalty |
| --- | ---: | ---: | ---: |
| single24 | -9.240 ms | -0.156 ms | +53.937 ms |
| boundary4 | +93.690 ms | +80.834 ms | +141.364 ms |
| all48 | +1,302.869 ms | +1,313.867 ms | +1,356.192 ms |

Each penalty is compiled minus the mean of its two adjacent restored controls,
then the median across three scenes. Negative means faster. Single24 is
inconclusive/neutral, while boundary4 and all48 lose speed. All48 warm previews
were 7.803, 7.782 and 7.718 seconds. Most adjacent controls were about 6.4 seconds;
the last bird control drifted to 7.410 seconds. Small samples and drift limit
precision, but all48 lost on each matched pair. There is no speed promotion.
Node intervals are approximate client event timings, not synchronized kernel
measurements. Raw archive readiness is distinct from lossy preview readiness.

The native gates qualified both stages for all 53 retained block routes:
106 graph receipts, each retaining 15 native RMS, six sigmoid and two tanh-GELU
sites. The six shared generated wrappers each preserve those same call counts;
wrapper count is not the block coverage count. Native BF16, 256x256 final,
25 frames at 24 fps, 8+3 steps, original checkpoint and strict determinism
remain unchanged. The private compiler entry frames avoid the shared-forward
cache limit without changing the default Dynamo limits of 8/256.

PID39793 on packet06 remained healthy and ended on restored dispatch with all
three compiled candidates retained. The queue was empty, kernel postflight
clean and no FAULT latch present. Client exit code was zero. This experiment
used one controlled application replacement from PID17769, on the same host
boot; it did not reboot the computer or change power/memory settings.

The [complete summary](../data/multiblock-screen-01/summary.json) includes every
request timing, exact comparison, source identity, graph coverage and paired
calculation. The [inventory](../data/multiblock-screen-01/inventory.json) binds
3,233 text files in the 5,152,843-byte compressed evidence archive. SHA256:
`efe4ffcdb76499f2228c06e43f7eca9241a2f0d430827eb800c1903fcc0302df`.
Raw tensors, media, weights and binary caches are excluded from Git. Verification
preceded pruning redundant captures; only three recent previews are retained.

Native invocation from this lane:

```bash
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/steve/.venvs/ltx25-baseline/bin/python scripts/run-multiblock-screen-v1.py \
  --campaign multiblock-screen-01 \
  --packet /mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-compiler-06 \
  --manifest-sha256 3676b1e47b514f5c28597063b42c9806ed13639cc2dde0f3b25fd44564c08394 \
  --server-run /mnt/fast-ai/bench-results/ltx25-baseline-20260913/encoder-server-compiler-06
```

Client verification used one CPU thread; server Torch threads stayed at 16.
The full local evidence root is `/mnt/fast-ai/bench-results/ltx25-baseline-20260913`.

Next: the [adjacent-state reuse candidate](adjacent-state-reuse-03-cpu.md)
removes duplicate validation work without moving any correctness boundary.
CPU qualification passes; its native exactness and speed remain unmeasured.
Continuous generation and the under-one-second goal remain incomplete.
