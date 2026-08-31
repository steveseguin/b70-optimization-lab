# Qwen3.8 repaired TP2/MTP1 D61 startup failure

Date: 2026-08-31

D61 produced no benchmark result. Both ranks loaded the model, but rank 1 lost
its Level Zero device during vLLM's profile-run dummy sampler, specifically
while `SpecDecodeMetadata.make_dummy` created its draft-token tensor. No HTTP
request was served, so no decode, TTFT, acceptance, quality, or determinism
number may be inferred from this attempt.

The failure was a Xe device event rather than a Python assertion or an
out-of-memory kill:

- the captured attempt journal contains 478 unsuccessful fault responses for
  PCI function `0000:e3:00.0`;
- the other B70, `0000:03:00.0`, subsequently logged one BCS engine reset;
- basic compute on the second B70 failed after the event despite its management
  status initially appearing normal;
- an isolated PCI function-level reset was attempted only after confirming
  that no process had the second B70 open;
- that reset did not recover the device. Xe then reported incorrect DMC state,
  a GuC scheduling-policy timeout, TLB-invalidation timeouts, a failed GT reset,
  and finally declared `0000:e3:00.0` wedged and needing recovery.

The shell exit code is 130 because the dead server wrapper was terminated after
the device-loss diagnosis; it is not the cause. The preserved server traceback
contains `UR_RESULT_ERROR_DEVICE_LOST`.

All further GPU experiments are paused for this boot. A full host reboot (or a
complete Xe driver teardown/reload that would also disrupt the desktop GPU) is
required, followed by independent basic-compute gates on both B70s. Only then
may D61 be retried. D59r/D60 remain the deterministic TP2/MTP0 comparator; D61
does not qualify or reject MTP1 performance and does not implicate the already
qualified M=512/no-barrier projection repair.
