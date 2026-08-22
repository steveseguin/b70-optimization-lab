# Qwen3.8 GPU3 incumbent-control health r2 result

Date: 2026-08-21

Classification: **`gpu3-incumbent-control-health-pass`; GPU3 stock-control
health is re-established post-recovery.**

Preregistration:
[`2026-08-21-qwen38-gpu3-incumbent-control-health-r2-prereg.md`](2026-08-21-qwen38-gpu3-incumbent-control-health-r2-prereg.md)
(adopting the frozen r1 contract; all four source hashes rechecked
immediately before the single launch).

## Outcome

The fresh-root physical-GPU3 stock-control diagnostic passed every gate
within the 60-second wall deadline. The worker receipt chain is complete and
exactly ordered: `worker-start`, `base-and-stage-verified`, `device-bound`,
`stock-maps-bound`, ten ordered `fa-launch-returned` receipts, `sync-enter`,
**`sync-return`**, and `worker-complete` — the two receipts r1 never produced.
The supervisor's independent `validate` subcommand reproduces the passing
classification (exit 0). The pre-launch kernel journal was quiet and the
post-run five-minute window contains **zero**
Timedout/Engine-reset/GuC-error/reject events: the prefix that reproducibly
collapsed GPU3 into a reset storm before today's host-wide `xe` recovery now
completes cleanly on the same boot as the recovery gate.

Preserved root `/home/steve/qwen38-gpu3-incumbent-control-health-20260821-r2`:

- `contract.json`
  `4ae1e3e467889a52afc851090d6793a2d4b3bb130ed23e0930e540d2c57e2ae4`;
- `terminal.json`
  `7c04155e969dbbc97b00268fe7bcbefda0b232feabdd47db817d26aa5a631ae2`;
- `worker-result.json`
  `d9865a09bb35f8651d0c5bfb9652dd7399ae98d5752ebcc2a5bfb81615aecce4`;
- `worker-phases/0015-sync-return.json`
  `8ba7fc948aa0e709e548fa54b074ebffc309212307b7151953b84c2ce4e5d1f5`;
- `worker-phases/0016-worker-complete.json`
  `e03b085c3faab51a02808e822583fad8c881c197777a2ec90ba46c9996535cdf`.

Worker boot ID `256bc838-c015-4c91-a8f9-363d281f7555` (same boot as the
recovery gate), PID/PGID/SID `1176457`, GPU3 UUID
`868023e2-0000-0000-4700-000000000000`, `0000:47:00.0`.

## What this authorizes

Per the frozen contract: this pass says the stock KV-128 launch/synchronize
prefix completed once on post-recovery GPU3, and it authorizes **writing a
new preregistration for a completely fresh two-GPU eight-arm Q64xK32
operator campaign** (GPU2 and GPU3, fresh roots, no carry-over of the
terminal Q64xK32 r2 GPU2 packets). It does not authorize that campaign's
launch, any candidate/model/full-25 run, or the blocked mtp.fc INT4 screen's
own remaining prerequisites. The r1 root and the Q64xK32 r2 root remain
terminal and preserved.
