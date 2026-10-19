# Two-card draft line closed: the draft is near its roofline (≤ +2.3% even at full closure)

On bundle 8 (58.798 tok/s), rank 0 waits ≈ 1.23 ms/interval for rank 1's draft (packet154). We checked whether the draft could be made faster or moved:
- **Moving draft work into rank 1's suffix slack** (packet156): ceiling ≈ 0.3%. Closed on CPU.
- **Moving a layer to rank 0** (packet120, earlier): −3.9%. Closed.
- **Speeding up the draft's kernels** (packet158 roofline): the draft's kernels total ≈ 1.38 ms, and closing every gap to the copy-bandwidth reference would save ≈ 0.48 ms. That is about +2.3% at 100% transfer and ≈ +0.45% at the lab's usual 20%. The head is already at its reference.
- **Host issue batching:** issue time (1.571 ms) is only ≈ 0.19 ms above kernel time, worth ≈ +0.9% at most. Packet34 found graph replay neutral.

Packet157's device decomposition failed its smoke three times on analyzer details after exact device runs, so it was not repaired a fourth time (hourly review 37).

**Decision:** the draft line is closed. The DO-NOT-REPEAT row is in `experiments/own-xpu-runtime/stage2/packet158-draft-levers/DO-NOT-REPEAT.md`. The two-card record stays 58.798. The next two-card work needs a mechanism that changes the pipeline's critical path itself, not another kernel pass.
