# Packet58u: measured one-card host admission

CPU-only policy bundle for **the next new one-card packet**. Packet58r,
packet58t, their seals, existing windows, proposals and queues are unchanged.
This bundle launches nothing. A memory pass is not coordinator authorization.

| View | Accounted peak used (GB) | Host bound (GB) | Required MemAvailable (GB) |
| --- | ---: | ---: | ---: |
| Production | 82.515945 | 86.810912 | 95.400847 |
| tile16 | 82.516125 | 86.811092 | 95.401027 |
| tile16 + resident lookups | tile16 + explicit substitution below; unmeasured | 86.811092 | 95.401027 |

GB here means 1,000,000,000 bytes. Each host bound is the maximum retained,
normalized sample plus **4 GiB = 4,294,967,296 bytes**. Admission adds the
unchanged **8 GiB = 8,589,934,592-byte reserve**. All windows retain whole-host
ownership. K1 alone keeps its existing 12 GiB admission and 4 GiB shadow cap.
Exactness windows use the same full-file allowance as timing; there is no
separate lower empirical exactness admission.

## Receipts and accounting

[`measured-peaks.json`](measured-peaks.json) pins 29 complete windows from
58g, 58k, 58n and 58p, including 15 full-model windows and 14 K1 fixtures.
It records every sample count, peak witness/line, native after-load check and
source hash. Production uses eight full-model windows; tile16 uses six.
58k's port is retained as a diagnostic cross-check, not relabeled tile16-only.
The derivation reads **every** supervisor sample, including load and drain,
and checks each full-load census for the complete 18 GB expert cache, pinned
expert bytes and full BF16 KV. An incomplete seed is not used as a full-load
measurement. Native after-load shadow is checked separately.

The recorded `host_accounted_bytes` is a conservative accounting value, not
RSS or a measured physical working set. Timing receipts charge:

```
completed pinned experts + max(0, GPUActive - baseline - completed pins)
  + process-tree RssAnon + 33,323,087,360 bytes of nonexpert/file allowance
```

Exactness receipts charged no file allowance; the derivation adds the full
33,323,087,360 bytes before comparing them with timing. Maxima are computed
from simultaneous samples, not by adding independently timed component peaks.
All retained full-model shadow peaks are at most 657,899,520 bytes. The K1
maximum is 885,899,264 bytes. The new model shadow stop is 4 GiB, matching K1.
The extra 4 GiB is a policy margin, not a statistical worst-case guarantee.

For resident lookups, 58t's census specifies **29,321,610,240 anonymous bytes**.
They replace the same tensor bytes already inside the full-file allowance:

```
tile16 measured core peak                       49,193,037,824
resident lookup copy (design, not measured)      29,321,610,240
remaining nonexpert/file allowance               4,001,477,120
explicit margin                                 4,294,967,296
host bound                                     86,811,092,480
unchanged reserve                               8,589,934,592
required MemAvailable                          95,401,027,072
```

The resident design adds 29.322 GB to the measured **core**, not a second time
to the full-file accounted peak. Its actual anonymous bytes are charged in
full by the live sensor; no planned lookup bytes are subtracted from RSS.
Clean source-file pages remain naturally reclaimable as represented by
MemAvailable. No cache drop, advice, mlock or page warming is introduced.
This substitution is already the category treatment in frozen 58t's timing
plan; the new change is the measured core and explicit shadow margin.

The saved 14:58 UTC refusal retained **115,481,063,424 bytes available** in
its error, not a complete `/proc/meminfo` snapshot. The old requirement was
118,308,908,048 (short by 2,827,844,624). New tile16/resident admission leaves
**20,080,036,352 bytes** above its requirement. No missing sensor value is
invented in that historical fixture; this is an offline arithmetic replay.

## Copy forward into a new sealed packet

Copy this entire directory as a private subdirectory of the **new** packet.
Verify `seal.json`, then pin that seal and its files in the new packet's build
manifest. `memory_plan.py` imports only the standard library and loads local
sealed metadata; it does not import any frozen launch module. The old source
paths in the evidence remain provenance links. Select the allocation view
explicitly: `production`, `tile16`, or `tile16-resident`. Do not select the
sparse profile for a process that retains resident copies during its control
arms. One process with mixed views must reserve its largest lifetime footprint.

In the new window copy:

1. Call `window_plan(window, view=allocation_view)` before admission and
   `admit(meminfo(), budget)` at both existing admission points, including
   after drain waits. `admit` checks memory only; retain the actual whole-host
   lease, paused/drained lane B, memory fence, device masks, native allocation
   census, disk checks, fault checks and quality gates.
2. Feed that **same budget** to the existing live accounting function, or use
   this module's `live_memory_sensor` with the existing checked process-tree
   sampler, completed/census-checked `PinnedExpertProgress`, admission observer
   and sample log. Keep the sampler's exited-root handling. Read completed pin
   progress before host sensors. Never credit a bank still being allocated.
3. Keep the supervisor's cooperative stop and native drain. Sensor errors,
   MemAvailable below 8 GiB, shadow above 4 GiB, and combined accounting above
   the host bound stop the job. Save the offending sample before requesting
   stop. Existing anonymous-memory guards also remain. Do not add restart,
   retry, hard-kill or settings changes.
4. Retain the native `after_load` + full census validation. The original
   `postload_observation` may continue using its frozen legacy seed helper for
   reporting, but it must not feed that seed back into this policy. New
   observations cannot silently reduce a sealed bound. Do not replace an old
   module import wholesale: legacy `exact_plan`/`seed_observation` report
   interfaces and packet-specific window plumbing are deliberately not changed
   here. Complete the future packet's argument and whole-window CPU gates
   before sealing it.

Scope: this model/quantization, one card, target-only decode, 18 GB expert
cache, existing 4K BF16 allocation, and the retained workloads capped at 128
generated tokens. Different runtime/driver/topology, cache, context, MTP,
extra resident allocations or longer generation need a new bound review and
new seal. The live stop protects this empirical policy; it is not proof that
unsampled peaks or another driver have the same memory behavior. Resident
device admission/performance and next-packet integration remain unrun.

## CPU reproduction

From this directory, with no GPU activity initiated by these commands:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B derive.py --check </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B seal.py </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B test_memory_plan.py </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B memory_plan.py --view tile16 --window WSCREEN </dev/null
```

Tests replay all retained samples; add the full resident design increment
synthetically; exercise exact admission/live-stop boundaries; reject edited
budgets and seals; and feed sensor failures into the **original supervisor
function** with a fake child, proving saved errors precede one SIGTERM and no
hard kill. The resident samples in tests are labeled simulations and never
enter a device-result directory. [`evidence/cpu-tests.json`](evidence/cpu-tests.json)
records pass/fail, seal hash, RSS and CPU placement.

[CPU closeout](CPU-CLOSEOUT.md) · [Do not repeat](DO-NOT-REPEAT.md)
