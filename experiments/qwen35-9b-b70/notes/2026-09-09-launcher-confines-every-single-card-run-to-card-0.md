# The shared launcher silently confines every single-card run to card 0 (2026-09-09)

`repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-server.sh` sets **both** device variables from one
value:

```sh
-e ZE_AFFINITY_MASK="${xpu_device_mask}" \
-e ONEAPI_DEVICE_SELECTOR="level_zero:${xpu_device_mask}" \
```

These compose rather than agree. `ONEAPI_DEVICE_SELECTOR` filters the visible device set;
`ZE_AFFINITY_MASK` then indexes **within that already-filtered set**. For `XPU_DEVICE_MASK=0` the
index 0 resolves and everything works. For any non-zero card the index is out of range and the
device disappears.

Measured in the R276 image, allocating a real tensor on each combination:

| `ONEAPI_DEVICE_SELECTOR` | `ZE_AFFINITY_MASK` | result |
| --- | --- | --- |
| `level_zero:0` | `0` | OK |
| `level_zero:1` | `1` | **No XPU devices are available** |
| `level_zero:3` | `3` | **No XPU devices are available** |
| `level_zero:1` | `0` | **No XPU devices are available** |
| `level_zero:3` | `0` | **No XPU devices are available** |
| `level_zero:1` | unset | OK |
| unset | `1` | OK |

Either variable alone is correct. Setting both is correct only for card 0.

## Why it went unnoticed, and why it cost four hours here

Every published single-card campaign in this lane used `XPU_DEVICE_MASK=0`, the one value that
works. Nothing was wrong with any published result; the bug only appears when someone tries to use a
second card for a single-card run, which this four-card host is the first to do.

**`torch.xpu.device_count()` is a lying diagnostic here.** Under the broken combination it returns
`1` - the device appears present - and only a real initialisation fails:

```
count 1
RuntimeError: No XPU devices are available.
```

Three separate probes were built on `device_count()` and all three passed, which disproved the
correct hypothesis twice before an allocation probe reproduced the failure in one attempt. Probe
with work, not with a count.

## Status and the fix

Not fixed here. `run-server.sh` is referenced by at least six published packages, and changing a
shared published recipe in the middle of an unrelated optimization grind is the wrong way to land
it. The correct change is to translate the mask to **positional** indices for `ZE_AFFINITY_MASK`
(`"1"` -> `"0"`, `"2,3"` -> `"0,1"`) or to drop one of the two variables, plus a TP2 regression run
on a non-zero card pair, which is a reviewable change of its own.

Consequence for this campaign: **all arms run serially on card 0.** Three of four cards are idle,
which costs wall clock and buys something back - every timed row is now measured on a quiet host, so
a P2 screen is close to a verdict rather than a rate taken while three neighbours held cards.

Note `"2,3"` fails for TP2 by the same arithmetic, so this also blocks any future two-card lane that
is not pinned to cards 0 and 1.
