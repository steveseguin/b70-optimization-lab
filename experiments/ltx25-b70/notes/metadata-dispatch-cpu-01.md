# Metadata dispatch attribution: first CPU fixture rejected

September 14, 2026. The CPU-only attribution stopped during fixture construction
before dispatch or timing because the tiny fixture did not match the native
84-parameter/buffer census. It inherited both feed-forward bias defaults from
the earlier generic CPU lifecycle fixture. The frozen native block00 receipt
instead has no video feed-forward biases, while both audio feed-forward biases
are present. This is a test fixture issue, not a model/runtime fault.

The process exited1, XPU remained uninitialized after import, and the active
LTX server was untouched. No compilation, block forward or numerical generation
ran. Preserve [failure](../data/metadata-dispatch-cpu-01/result.json) and
[preregistration](../data/metadata-dispatch-cpu-01/preregistration.json).
The tested script and adapter snapshots are at
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/metadata-dispatch-cpu-01`.

The successor must set `ff_bias=False, audio_ff_bias=True`, compare registered
state names against the pinned native receipt, and record observed census before
assertions. Do not weaken the expected84 guard to accept the wrong architecture.
No speed conclusion is available from this failed setup.
