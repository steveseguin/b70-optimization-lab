# Coordinator screen, then conditional full chain

This agent performed CPU work only. The coordinator owns GPU scheduling,
health admission and any actual run. Packet58/card0 must finish and release
its pinned memory before the TP2 screen. Do not stop it to make room.

Run from `/home/steve/llm-optimizations`. Set `REVIEWED` to the coordinator's
actual reviewed-through UTC timestamp. Use a new output and unit name on each
new authorized candidate; never retry a failed launch automatically.

```bash
P=experiments/own-xpu-runtime/stage2/packet59-fast-draft
S=experiments/own-xpu-runtime/stage2/screen
: "${REVIEWED:?set the actual coordinator fault-review UTC timestamp}"
systemd-run --user --unit=screen-p59-a --collect \
  --working-directory=/home/steve/llm-optimizations \
  nice -n 19 taskset -c 4-15,20-31 env OMP_NUM_THREADS=2 \
  python3 -B "$S/screen.py" \
  --profile tp2 --lineage "$P" \
  --binary "$P/build/device/own-rt-iq3" \
  --dispatch "$P/dispatch-speed6.json" --seal "$P/build-receipt.json" \
  --output "$S/evidence/p59-a" \
  --faults-reviewed-through "$REVIEWED" --authorized-device-window
```

For CPU-only command/seal inspection, invoke the same Python command directly
with `--plan` instead of `--authorized-device-window`; no service is needed.
The plan does not establish current device or memory admission.

The screen does one model load, a separate 64-token incident check and twelve
cold 128-token requests with reset between them. It verifies every token
against the packet49 oracle and retains timing and draft acceptance data. It
is diagnostic, never submission evidence. The fixed response scope is 128,
not a strict 512-token final gate.

Proceed to a new full packet56-style chain only if all 12 prompts are exact
and the class-balanced 99-interval rate exceeds **46.962697 tok/s**. Keep the
same weights, full target head, dispatch, selection, 23/25 split, draft rank1,
BF16 KV and `iq3-p49-split32-v1` oracle. Use this packet's CPU draft arithmetic
for draft KD expectations; packet56 draft logits are no longer its oracle.
Screen seals cannot stand in for full-chain seals. The coordinator must prepare
that conditional chain's separate binding and submission lineage after the
screen passes; do not relabel this screen as the chain or run packet56's binary.
