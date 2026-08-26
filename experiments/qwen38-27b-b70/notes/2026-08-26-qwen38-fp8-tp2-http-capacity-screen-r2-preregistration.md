# Qwen3.8 official FP8 TP2 active-slot capacity screen R2

Status: **preregistered diagnostic; not launched**.

R2 repeats p8, p16, and p32 on three new fresh servers. R1 p8 is excluded from
selection and publication because its frozen cleanup classifier falsely
matched the still-running timeout parent. R2's only protocol change parses the
matched PID field and excludes the exact runner and timeout-parent PIDs.

Everything else remains frozen: official FP8 revision, digest-pinned vLLM
image, TP2, target-only/MTP0, FP16 KV, 4,096-token capacity, 256 batched-token
limit, prefix cache off, size-one graph capture, unique p128/g128 requests,
compact output oracle, and c1/2/4/8/16/32/64 ladder. Each response must return
128 raw token IDs with zero cached prompt tokens and no cross-base oracle
collision. Each attempt must also remove its container, leave no model process,
and close its port.

R2 remains a one-attempt-per-profile diagnostic. Its winner needs at least 5%
more aggregate throughput than qualified p4 at its own unqueued capacity point,
then two additional fresh-server confirmation attempts before publication. No
R1 value enters an R2 aggregate, and no point is interpolated or extrapolated.

See the [machine-readable contract](../data/2026-08-26-qwen38-fp8-tp2-http-capacity-screen-r2-prereg.json).
