# Qwen3.8 TP2/MTP1 strict D68 dummy-repair device loss

Date: 2026-08-31

D68 restored the M=512 projection repair on the D67-stable profile-only image.
It failed during the first synthetic 256-token profile forward before sampler,
readiness, or any inference request. Both ranks passed layer 0 and reached the
layer 1 dense MLP; rank 1 then surfaced `UR_RESULT_ERROR_DEVICE_LOST` at the
post-MLP decoder barrier. The log contains 30 decoder begins but only 28 passes.
The timestamp-bounded Xe journal contains 491 unsuccessful fault responses,
five CCS CAT errors, and one reset on PCI function `0000:e3:00.0`.

The direct model-integrity gate passed. Teardown was manually accelerated only
after device loss was conclusive, so the attempt exit is 130 and no metric or
partial performance evidence exists. Both B70s subsequently reported normal
state and independently produced identical finite matrix results.

The contrast with D67 isolates the immediate trigger: the correctness hook was
padding random dummy profile rows into the M=512 projection path. Synthetic
dummy output has no user-visible correctness requirement. D69 therefore adds a
scoped `_dummy_run` marker and bypasses projection repair only while that marker
is present. Real request rows retain the repair. This is preregistered and must
pass startup before any strict retry.

Raw evidence:
`/mnt/fast-ai/bench-results/qwen38-tp2-mtp1-profile-only-strict-20260831-d68/`.
