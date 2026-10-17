# Packet59b: INT8 draft prefix head

Scope: CPU-only 75-minute preparation, independently from packet56. No GPU,
model payload read, sudo, service, host-setting change or device discovery.
All compiler/test helpers run at nice19 on cores 8–15,24–31, with python3 -B
and OMP_NUM_THREADS=2. No other worker's packet is edited.

The new separate draft head contains 233,963,520 signed-byte codes and
365,568 bytes of FP32 row scales. It is constructed once at load from the
same decoded Q6 source weights and used only for proposals. The target's
full head and arithmetic remain unchanged and verify every emitted token.

The retained packet56 census shows only 89,364,320 bytes available on rank1
inside the 30 GiB arena. The new head would exceed that by 144,964,768 bytes.
The implementation therefore moves the complete draft to rank0 using the
existing reverse-handoff/controller protocol; it allocates only the INT8
prefix there, eliminating the need for a duplicated full target head.
The target remains split 23/25 at 4K with full BF16 KV and unchanged states.
The existing rank0 placement's larger target scratch is retained, not shrunk.
Planned arena margins are 2,063,953,442 / 3,183,681,686 bytes. This is allocation
accounting, not a device residency result.

The brief's BF16 description does not match the production source: expanded
Q6 stores signed-byte codes and FP32 scales per 16 columns, plus metadata.
The candidate reduces unique bytes consumed by the head from 3,200 to 2,564
per row (19.875%). The supplied 521 us measurement would imply roughly
104 us kernel savings if bandwidth alone governed it, not a measured gain.
Moving the draft and changing acceptance can outweigh that estimate.

The A/B must be labeled INT8 plus rank0 draft placement. The candidate's
transport writes the requested/effective rank mapping before loading;
actual native launch receipts and census use rank0. Screen outputs remain
strictly diagnostic and cannot be submitted as record evidence.

Initial git pull --rebase was blocked by other workers' unstaged/staged
changes. Fetch showed no incoming main commits at that point; their files
were neither stashed nor edited. A later pull attempt also found another
worker's staged files. Commits use explicit packet/note paths only.

Build and CPU gate results are recorded in the packet receipts. The first
native compile caught an int-to-unsigned initializer narrowing in the new
head call; an explicit validated width cast fixes it. Its log is retained
under this packet's build scratch. No device binary was executed.

[Implementation and memory details](../experiments/own-xpu-runtime/stage2/packet59b-int8-head/README.md),
[coordinator command](../experiments/own-xpu-runtime/stage2/packet59b-int8-head/WINDOW.md).

## Final preparation result and screen blocker

Both native and GNU host builds pass. Two fresh draft fixture processes agree
on all 257 full-width INT8 logits, code bytes, FP32 scales and argmax IDs.
The 257 Q6 target-head logits match a reference compiled directly from sealed
packet56 sources. All **32 miniature target layer fixtures** and eight output
tokens match packet56 byte for byte. Two fresh rank0-draft integration runs
retain those target fixtures and deterministic proposal IDs, exercising six
hits and one ordinary miss in this synthetic case. These counts are branch
coverage, not model acceptance evidence. The initial CPU assertion incorrectly
expected proposals during prompt reading; the corrected gate requires them
from the generation boundary and checks provider errors at every position.
The failed test evidence is retained under the candidate's own build tree.

The final lean seal verifies:
`e93a32fd9a798d0c850c1e049b0a21d09a98627cdc49c63bf3954d6bc478f918`.
[CPU fixture receipt](../experiments/own-xpu-runtime/stage2/packet59b-int8-head/fixture/receipt.json),
[immutable screen seal](../experiments/own-xpu-runtime/stage2/packet59b-int8-head/screen-seal.json).
No device execution, device acceptance number or performance result exists.

**The coordinator's screen is blocked on a wrapper profile update.** Screen
v2 landed at `ddd15c4bd` while this packet was being prepared. Its CPU-only
A/B plan check returned exactly:

```text
REFUSED: tp2 allocation envelope changed
```

`screen/v2/common.py` requires the candidate memory-plan JSON to equal
packet56's entire plan; this candidate declares the different rank0 allocation
layout above. The sealed engine is preserved. Do not bypass that guard or
use the older wrapper to evade it. The screen owner needs to register and
validate this rank0-draft placement and its conservative per-rank/host budgets,
including the approximately 0.945 GiB higher combined allocation, while
retaining the current health, storage, census and graceful-drain checks.
The generic screen currently requests draft rank1; this candidate maps it to
rank0 and records both values before native launch, so the new profile should
also expose the effective placement in its identity. Alternatively, keep the
packet parked and prepare a separate rank1-compatible design; rank1 is short
144,964,768 bytes, so a direct additional allocation there is not viable.

The exact command below is the handoff command **after that profile is
admitted**. It is currently expected to refuse at preflight. Run only in the
coordinator's admitted `screen-*` user unit, with the conditions in WINDOW.md:

```bash
P=experiments/own-xpu-runtime/stage2/packet59b-int8-head
S=experiments/own-xpu-runtime/stage2/screen/v2
taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 python3 -B "$S/ab.py" \
  --x "$P" --x-seal "$P/screen-seal.json" \
  --y experiments/own-xpu-runtime/stage2/packet56-draft-prefix \
  --output "$S/evidence/packet59b-v56-ab-a" \
  --fault-review "$REVIEW" --authorized-device-window
```

After removing only this packet's regenerable object/dependency files, the retained build is 67,897,089 bytes (below the 600 MB cap). Compiler logs, command files, checked sources, binaries and failed-test evidence remain. The unchanged 4 MiB RoPE constant is a hash-verified read-only link to packet56; no duplicate large constant is committed.
