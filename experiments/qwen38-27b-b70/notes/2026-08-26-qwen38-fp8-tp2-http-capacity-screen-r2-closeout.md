# Qwen3.8 official FP8 TP2 active-slot capacity screen R2 closeout

Status: **closed diagnostic; no R2 profile is publication evidence**.

The p8 and p16 attempts passed the frozen output-isolation and cleanup gates.
At their respective unqueued capacity points they measured 155.1503 and
280.9980 aggregate tok/s. Those are 91.34% and 246.54% above the qualified p4
control's c4 value of 81.0867 tok/s.

The p32 attempt returned 128 token IDs for every response, used zero cached
prompt tokens, and produced no cross-base frozen-oracle collision. Its c32
observation was 469.8559 aggregate tok/s, but it is excluded: the frozen
cleanup classifier matched the temporary outer orchestration shell and wrote
`process-survived`. The actual container, listener, and model processes were
gone after the run, which identifies a classifier defect but does not permit a
retroactive pass.

R2 therefore selects p16 as its highest contract-valid diagnostic. The large
p32 observation justifies two wholly new p32 confirmation attempts under a
classifier that ignores shell and timeout wrappers by executable name. The R2
p32 value is not reused in the confirmation aggregate. No R2 result is
interpolated, extrapolated, or published.

See the [machine-readable closeout](../data/2026-08-26-qwen38-fp8-tp2-http-capacity-screen-r2-closeout.json).
