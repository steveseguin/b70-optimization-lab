# Qwen3.8 Flash-Next FP8 production-M1 MoE warps-8 component result

Date: 2026-08-30
Status: lossless component positive; endpoint qualification pending

The preregistered real-weight M1 screen passed. It used the production
512-global/128-local expert mapping, layer-0 rank-0 checkpoint weights, three
hidden seeds, and fresh-process default/candidate/default brackets. Every arm
retained one hash through 100 repeats; all 300 hashes within each seed matched.

Changing only `num_warps` from 4 to 8 reduced median component latency:

- seed 20260826: 449.441 us bracket mean to 407.759 us, 9.27%;
- seed 20260827: 449.602 us to 408.260 us, 9.20%;
- seed 20260830: 449.120 us to 411.104 us, 8.46%.

All three clear the frozen 5% gate; median reduction is 9.20%. A separate
tuned-folder run, with no explicit candidate override, resolved batch-size key
M1 to `num_warps=8`, retained the seed-20260827 authority hash, and measured
418.433 us. This is the effective-key receipt A27 lacked. The dedicated map
changes only key `1`; M4 and every other entry retain their defaults.

The first attempt failed before weight load or compilation because it combined
two incompatible device selectors in a sanitized environment. It has no
performance credit. The corrected attempt used the same stage/device identity
as the endpoint and completed without a model load, reboot, host-memory
pressure, or device fault.

This is a strong, exact component result, not endpoint tok/s. The next endpoint
arm must bind the M1-specific map and emit the selected key plus effective
configuration, then pass recovery, semantic, 16-repeat, short authority,
cache-zero, needle, and two-row exact-4K gates. A27's file-load-only receipt
must not be reused.

Structured result:
[`20260830-moe-m1-warps8-component-positive.json`](../data/20260830-moe-m1-warps8-component-positive.json).
