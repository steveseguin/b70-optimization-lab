# Flash-Next BF16 deterministic A4a census preregistration

Date: 2026-09-02
Status: frozen before device execution

## Objective

A3 made `torch.backends.mkldnn.deterministic=True` exact within and across two
fresh processes for the real layer-0 `hc_down_inject` M=1 shape, while native
produced 100 active hashes in 100 sweeps. A4a tests whether that supported
provider control generalizes across every BF16 dense projection family used by
Flash-Next target decode and whether its multiplicity-weighted cost is
non-regressive. It is component evidence only and cannot authorize an endpoint
change, speed claim, or quality claim.

## Frozen dependencies

- A1 14-family catalog/real-weight loader SHA-256:
  `e4700fc44a65d71c7b0a7df5ff34924d808ba685c4157b0e2c12fd4b9d4bdf22`;
- A3 tool SHA-256:
  `8ddd0dae1b1a1153bc9c791c9192df87ed0daeb1dcdc7f73313564e8e16dca57`;
- A3 tracked result SHA-256:
  `82c71fafec724369d4fd58d8e6ab1948db4ca75db8b9285de0e51710f22f2bef`;
- A4a tool SHA-256:
  `c2caf7427a229f2d0a3158aa41aefacfddf0d3ccb368946feb01bc8bb5147184`;
- A4a test SHA-256:
  `e1660f61c9f75955f16e133b3768a86f8ec65f3db413ba2586ad1773af00ae6c`;
- model `Qwen/Qwen3.8-Flash-Next-FP8`, revision
  `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`;
- Torch `2.11.0+xpu`, Git
  `70d99e998b4955e0049d13a98d77ae1b14db1f45`, and installed
  `libtorch_xpu.so` SHA-256
  `ee584edab22b995637c5f6ec83fc10dea5931469c86cf2ad91952bb3e1108290`.

The A1 shard contract, checkpoint receipt, source/runtime identity, one-B70
selector, exclusive component lock, Gen3 clearance, mount, SMART, AER, memory,
and swap gates remain mandatory. Only `hc_down_inject` has synthetic padding:
columns 0:324 are active and 324:336 are a required exact-zero tail. The other
13 families use their full N as active output.

## Frozen matrix and ordering

The catalog has 14 families, two real sentinels per family, and exact production
multiplicities summing to 532 calls per target token. Each of the 28 canonical
cells gets two native and two deterministic fresh sequential processes, or 112
processes total. Even-index cells use native-1, deterministic-1,
deterministic-2, native-2 (`ABBA`). Odd-index cells use deterministic-1,
native-1, native-2, deterministic-2 (`BAAB`). Across the census, each arm
occupies each ordinal position exactly 14 times.

Each process independently reconstructs one real weight and the same 256 fixed,
distinct BF16 input rows. The backend flag is applied and read back before the
first GEMM and restored afterward. After four unreported complete-order warmup
sweeps, the process records 100 complete M=1 ordinal sweeps. Evidence includes
every sweep's full, active, and tail hash; all 256 full-row and active-row hashes;
per-row tail hashes where a tail exists; exact-zero tail state; and synchronized
XPU-event latency. Timing metadata is excluded from output authority.

Deterministic exactness requires one active result within each process and
across both processes. When native varies, every deterministic whole-row active
hash must occur in native support for that same ordinal row; this is stronger
than testing selected coordinates. The combined deterministic 256-row aggregate
need not occur natively because A3 demonstrated the expected combinatorial
aggregate mismatch. When native is stable, deterministic must equal it.
Scientific exactness failures are recorded and do not stop later cells while
health remains sound. Identity, setting, provider, mutation, non-finite output,
or health failures stop the plan after preserving child/parent envelopes and
postflight. Every failure after result-root creation—including deadline,
pre-cell health, directory, postflight-write, final-health, summarization, and
summary-write failures—also preserves a top-level `plan-status.json` with the
exact stage, current process, completed process prefix, primary error, and a
fresh final-health attempt.

## Frozen cost gate

Sweep event latency is divided by 256 to obtain M=1 call latency. Each cell uses
the median of its two replica medians; each family uses the median of its two
sentinels. Central target-step cost is `sum(calls_per_token * family_latency)`.
The summary also reports per-family sentinel minima/maxima and the corresponding
weighted total sensitivity bounds.

The candidate passes cost only if every condition holds:

1. central deterministic/native weighted ratio is at most `1.000`;
2. a 10,000-replicate, seed-`2026090204` family-cluster bootstrap—retaining both
   sentinels and replicas and their catalog multiplicity—has one-sided nearest-
   rank 95% upper ratio at most `1.010`;
3. both ABBA-even and BAAB-odd weighted half ratios are at most `1.020`;
4. no sentinel point from a family with at least 12 calls/token has a ratio
   above `1.020`.

This is a conservative non-regression screen, not speed credit. Advancement
requires all 28 exactness/parity cells and the entire cost gate. Even a pass can
authorize only a separately preregistered endpoint candidate.

## Safety and evidence

Execution requires `Q38_BF16_DETERMINISTIC_A4A_EXECUTE=YES`. The no-clobber
evidence root is:

`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/bf16-deterministic-census-20260902-a4a`

The plan performs no server or full-model load, reboot, container work, service
change, or live source modification. No outcome can revise protected results.
