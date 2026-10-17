# Packet66: second-token MTP acceptance probe

Packet66 is prepared and sealed for the coordinator's lane-B screen. It copies
packet61x into its own folder and adds a discarded second MTP pass. No GPU or
model run took place. The record stays **51.03 tok/s**, packet61x run
`cmvco3d6606u1le01941ek8hq`.

The first draft is published unchanged. At the next safe command boundary,
the probe saves every mutable draft buffer, reuses the official MTP layer
with its own first-pass hidden output and d1 embedding, logs d2, then restores
the saved state. d2 never reaches the target, its KV or the token stream.
The Qwen MTP architecture and recursive-reuse idea supplied in the owner's
brief are credited in the packet. Implementation is independent lab code.

Two fresh small CPU fixture runs match the original packet61x draft's d1
proposals and state across 68 steps each. They cover callbacks, pooled cache,
attention extent boundaries and request reset. The production-shape target
fixture also matches packet61x byte for byte; 136 target source files are
unchanged. Both runs' discarded d2 proposals agree. No full CPU model or
multi-hour qualification was run.

One premise needed correction: packet61x emits one token per pipeline
iteration and schedules target rows separately. It has no batched M=2
verifier. The reviewed receipts also contain no matched M=1→M=2 GDN increment.
The cost report says this explicitly rather than inventing that measurement.

Existing route and timing receipts give an optimistic partial extra-row cost
of **4.129 ms** if the two ranks overlap, or **7.986 ms** if they run serially.
The model includes additional expert reads and serial GDN work, but omits
other verifier costs. It uses the retained control's **1.906 ms** draft wall
time as a second-pass assumption until the screen measures it.

| Assumed a2, not measured | Conditional projected tok/s | Change |
| ---: | ---: | ---: |
| 0.55 | 54.07 | +5.96% |
| 0.60 | 55.03 | +7.84% |
| 0.65 | 55.99 | +9.72% |

**Do not build the full depth2 engine yet.** The +10% case is unproven and
needs a2 above roughly 0.658 even under that optimistic partial model.
Measured-a2 and ±0.05 rows remain null; the post-screen analyzer fills them
from the actual per-cycle logs and reports acceptance per prompt and class.

The frozen lane-aware screen admits cards **2+3**, cores **4–7,20–23**, and
keeps the packet49 exactness requirement for all 12 prompts. Expect about
**four minutes** of active work, plus coordinator hold/drain waits. Its
**3,600-second** watchdog exceeds the required 4× margin. No screen or service
was launched here, and no frozen tree was edited. CPU work used nice19,
cores 8–15,24–31, serial compilation and an 8 GiB address-space limit. Disk
space remained above the 10 GiB stop floor.

[Exact coordinator command](../experiments/own-xpu-runtime/stage2/packet66-mtp-depth2-probe/WINDOW.md),
[design and cost details](../experiments/own-xpu-runtime/stage2/packet66-mtp-depth2-probe/README.md),
[CPU closeout](../experiments/own-xpu-runtime/stage2/packet66-mtp-depth2-probe/CPU-CLOSEOUT.md),
[seal](../experiments/own-xpu-runtime/stage2/packet66-mtp-depth2-probe/screen-seal.json).

The host's loaded-card state did not change. CURRENT.md and the other jobs'
folders were left to their owners, as this brief limits writes to packet66
and this note. The next action belongs to the coordinator.
