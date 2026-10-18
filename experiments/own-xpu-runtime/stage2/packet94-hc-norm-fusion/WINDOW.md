# Packet94 proposed screen windows

Use the unchanged pinned shared v4 wrapper. Choose one complete direction;
the four files are proposals, not entries added to the live queue.

| Direction | First: complete grid | Then: winner confirmation |
| --- | --- | --- |
| B first | `experiments/own-xpu-runtime/ops/lane-queue/proposed-p94-B-grid.txt` | `experiments/own-xpu-runtime/ops/lane-queue/proposed-p94-A-confirm.txt` |
| A first | `experiments/own-xpu-runtime/ops/lane-queue/proposed-p94-A-grid.txt` | `experiments/own-xpu-runtime/ops/lane-queue/proposed-p94-B-confirm.txt` |

Each grid runs production / hc-normfuse / hc-normfuse+weightcache / production.
Confirmation runs production / the source lane's winner / production.
`--direction B-grid` selects B first; `--direction A-grid` selects A first.
Both keep 24/24 target layers, rank1 draft, token timing, 90-second gaps and
zero retries. Normal lane admission and fault review still apply at execution.

All 13 requests in every source screen must match the declared oracle, every
screen must retain the same per-prompt acceptance counts, and a candidate must
beat both fresh controls. Otherwise confirmation is refused. CPU planning
does not satisfy this device gate or authorize a performance headline.

All four proposals already passed `lanequeue.py plan` with queue files copied
into a temporary directory. See [queue receipts](evidence/queue-plans.json) and
[sealed screen plans](evidence/final-check.json). No live queue was modified.
