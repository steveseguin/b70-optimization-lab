# Native activation preservation: CPU qualification

September 14, 2026. Separate inactive candidate; the running LTX application is
unchanged. The native RMS candidate reduced audio discrepancies but failed the
first native block. This successor additionally preserves original sigmoid and
tanh-GELU calls as private opaque operations before Inductor.

The RMS dependency remains byte-identical at
09defae7340dc3d7f33e16ab80c76f22b6a2ae733617704f2e7b69086108d9fb.
The activation backend is
62b78186fdfc6d9a22cb8cb10423869ecc37cc09c9c0994a7ccebe2eafd41c2a.
It copies FX graph structures while retaining original parameter references;
all original compiler options and surrounding arithmetic remain unchanged.
Independent source review found no blocker for the captured static contiguous
inference graphs. No first-divergence or speed claim is made.

The focused CPU gate passed 21 checks: native BF16/F32 exact outputs/repeats,
fake/native canonical layout and non-aliasing; graph code and parameter object
identity preservation through both copies; exact rewritten output; rejection
of noncontiguous input, unsupported dtype, wrong GELU approximation, missing or
duplicate input, unknown keyword, and unexpected replacement counts.

The actual tiny BF16 BasicAVTransformerBlock compiled at video token counts
64/256, audio count 26 and seeds 17/123. All four cases matched eager video/audio
and compiled repeats exactly. There were exactly two compiled graphs, each with
15 RMS, six sigmoid and two GELU native calls. Independent emitted-Python AST
census confirmed those counts. Peak process RSS was 1,065,784 KiB. These are
32-wide CPU fixtures, not native 4096/2048 GPU blocks or full checkpoint results.

Evidence: data/native-activations-block-cpu-01/ and
data/native-activations-guards-cpu-01.json. Sources:
scripts/ltx_native_activations_backend.py,
scripts/test-ltx-native-activations-block-cpu.py and
scripts/test-native-activations-guards-cpu.py. Full CPU evidence remains under
/mnt/fast-ai/bench-results/ltx25-baseline-20260913/native-activations-block-cpu-01.

Next: prepare a separate immutable runtime and client identity, preserving all
native stage/repeat, four-output, ownership and bounded-retention checks. Full
GPU qualification remains pending. Do not edit packet04 or retry its failed
numerical gate. PID 12199 remains idle with clean postflight and no host FAULT.
No additional application replacement, computer restart, GPU request, power or
memory-setting change occurred during these CPU tests.
