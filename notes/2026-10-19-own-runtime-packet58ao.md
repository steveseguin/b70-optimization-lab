# Packet58ao — one-card compute-tail audit

October 19, 2026. **No new build clears the 2% evidence bar.** The useful
two-card target changes are already on the 31.97 tok/s one-card line except
the recurrence change. Its earlier one-card test was inconclusive. It does
not justify another run without new evidence.

The saved 58ah and 58aj requests replay to their recorded rates. A 2% gain
on 58aj needs about **0.613 ms less per token**. The broad scale-sharing idea
reaches only **1.18%** under the previous cautious assumptions. A more favorable
number requires a transfer assumption that the evidence does not support.

The 20.77 ms compute-tail number is a host wait from the older diagnostic,
including zero-copy misses. The current logs cannot break that wait into
individual kernels. The packet preserves a ranked diagnostic comparison and
marks current one-card class times unknown. It does not turn two-card timings
into one-card measurements.

[Packet58ao](../experiments/own-xpu-runtime/stage2/packet58ao-onecard-next/README.md)
contains the complete accepted-mechanism inventory, all requested negative-history
searches, real timing replay, exclusions and
[closeout](../experiments/own-xpu-runtime/stage2/packet58ao-onecard-next/CLOSEOUT.md).
Packet58am remains the separate next miss-path test. No packet58ap or device-ready
claim was created; the conditional build/queue/native-proof steps did not apply.

Preparation used nice19, cores 8–15/24–31, Python `-B`, closed stdin and a 4 GiB
process cap. The replay and eight checks use only small saved receipts and text.
No compile, GGUF/full-shape read, GPU, service, sudo, settings, existing packet
or ops edit occurred. Main was pulled successfully; starting HEAD and origin/main
both equaled `27ac4ba462f958349253cfcc0184cf80746c5f7f`. Existing dirty work,
including CURRENT and the 58y report, was preserved. The observed 58y bytes are
hash-bound as working-tree evidence. Only this new packet and note are committed
with `git commit --only`, followed by a push.
