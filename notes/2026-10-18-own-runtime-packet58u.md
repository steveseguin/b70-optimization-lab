# Packet58u: one-card admission from measured peaks

October 18, 2026, steve-b70s. CPU-only, main. Initial `git pull --rebase`
refused unrelated dirty orchestration files; `git fetch` confirmed HEAD and
origin/main both at `fa38e9f973172cfa915f25e2cc6a4b7b5d513967`.
All work is in the new
[packet58u policy bundle](../experiments/own-xpu-runtime/stage2/packet58u-host-admission/README.md)
and this note. Packet58r/58t and all frozen packet/ops trees remain untouched.
Concurrent working edits, including CURRENT.md, are preserved. No live state
changes, queue edits or model launches are part of this preparation.

The new required available memory is **95.401 GB**, down from **118.309 GB**.
The saved 14:58 refusal had **115,481,063,424 bytes available**. The old bound
refuses it by **2,827,844,624 bytes**; the new tile16 bound admits it with
**20,080,036,352 bytes** above the full requirement. These are byte-exact
calculations from the retained refusal, not a new host measurement. Only
MemAvailable survives in that refusal; missing sensor fields are not invented.

## Derivation

Every retained supervisor sample from the completed 58g, 58k, 58n and 58p
windows is checked: **29 windows, 9,398 samples**, including 15 full-model
windows and 14 K1 fixtures. Full-model receipts must prove complete native
after-load samples, pinned experts, the full 18 GB cache, BF16 KV and the
device allocation census. Native after-load shadow is checked independently.

| Packet | Largest original accounted sample (bytes) | Largest full-model shadow (bytes) |
| --- | ---: | ---: |
| 58g | 82,515,944,960 | 657,899,520 |
| 58k | 82,513,561,088 | 624,869,376 |
| 58n | 82,516,125,184 | 657,899,520 |
| 58p | 82,514,036,224 | 657,899,520 |

Accounted memory is not RSS. The timing receipt includes all pinned experts,
the sampled driver shadow, process-tree anonymous memory and a fixed
**33,323,087,360-byte file allowance**. Exactness receipts omitted that last
allowance, so they are normalized by adding it before comparison. Maxima use
simultaneous sample rows, not a sum of unrelated component peaks. K1's maximum
shadow is 885,899,264 bytes and is retained separately.

| View | Measured normalized peak (bytes) | Bound, before reserve (bytes) | Required available, including reserve (bytes) |
| --- | ---: | ---: | ---: |
| Production | 82,515,944,960 | 86,810,912,256 | 95,400,846,848 |
| tile16 | 82,516,125,184 | 86,811,092,480 | 95,401,027,072 |
| tile16 + resident lookups | Derived from tile16; resident peak unmeasured | 86,811,092,480 | 95,401,027,072 |

Each bound adds **4 GiB** to the measured maximum, and admission adds the
unchanged **8 GiB reserve**. The live shadow ceiling becomes 4 GiB, as in K1.
Device allocation/reserve, cache and KV budgets do not change. Whole-host
ownership remains required; exactness windows now use the same conservative
full-file allowance as timing. K1 admission stays at 12 GiB.

Resident lookups add **29,321,610,240 bytes** to tile16's 49,193,037,824-byte
measured core. Those same tensors already occupy 29,321,610,240 bytes of the
timing file allowance. As in 58t's original timing design, replace that part
with anonymous residency, leaving 4,001,477,120 file bytes; do not charge the
same lookup tensors twice. This is why the resident and sparse timing bounds
are equal. Actual anonymous copy bytes remain fully charged by the live
sensor. Clean source pages reclaim naturally through MemAvailable; no page
advice, pre-read, cache drop, mlock, swap or settings change is introduced.

The resident bound is a **design bound**, not a measured resident result.
The 4 GiB margin is explicit, not a statistical guarantee. Longer generation,
new context/cache/resident buffers, MTP, driver/runtime or topology changes
require a new review and seal. Existing whole-host, native identity, census,
quality, fault, memory-fence and cooperative-drain gates remain required.

## Implementation and validation

The sealed standard-library
[`memory_plan.py`](../experiments/own-xpu-runtime/stage2/packet58u-host-admission/memory_plan.py)
implements explicit per-view plans, admission, combined accounting and a live
sensor adapter. Its metadata is local, so the entire bundle copies forward
without importing frozen launch code. The next packet must bind its seal and
pass its own actual argument/window gates. No existing launch path has been
silently redirected. No observation can lower this sealed policy.

All **19 tests pass**, including:

- the actual old admission function refusing the 14:58 reading, with all three
  new profiles admitting it;
- every retained sample fitting with at least 4 GiB margin, and a clearly
  synthetic full resident-copy increment replay;
- exact threshold boundaries and rejection of changed budgets, missing
  sensors, unknown views and modified sealed files;
- low available memory, excess shadow and excess combined accounting flowing
  through the original supervisor function: the offending sample is retained
  before a single cooperative SIGTERM, with no hard kill;
- relocation of the sealed module to a temporary private copy.

Commands, run from the new bundle directory:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B derive.py --check </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B seal.py </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B test_memory_plan.py </dev/null
```

The tests recorded **26,804,224 bytes peak RSS**, nice 19, precisely the
requested helper-core affinity and bytecode disabled. The work reads small
tracked receipts/censuses only. No model payload, GPU, service, host setting,
queue, sudo, reboot, reset or external submission was touched.

[Derivation/source hashes](../experiments/own-xpu-runtime/stage2/packet58u-host-admission/measured-peaks.json),
[CPU test receipt](../experiments/own-xpu-runtime/stage2/packet58u-host-admission/evidence/cpu-tests.json),
[seal](../experiments/own-xpu-runtime/stage2/packet58u-host-admission/seal.json),
[copy-forward handoff](../experiments/own-xpu-runtime/stage2/packet58u-host-admission/README.md#copy-forward-into-a-new-sealed-packet),
[closeout](../experiments/own-xpu-runtime/stage2/packet58u-host-admission/CPU-CLOSEOUT.md).

Next: adopt this bundle only in a new one-card packet. 58r/58t remain sealed.
Resident device behavior and future-packet integration are unrun, and no speed
or quality result is claimed by this CPU task.
