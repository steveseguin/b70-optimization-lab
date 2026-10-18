# Packet104b handoff

The coordinator authorized the two TARGET gate/up screens despite failure of
the <=0.85 micro gate. Preserve that failed result and the explicit
[override](screening-override.json); no other arm advances.

Use the new proposals `ops/lane-queue/proposed-p104b-B-grid.txt` and
`ops/lane-queue/proposed-p104b-A-confirm.txt`, relative to the own-runtime root.
The B order is production / gate-tile16 / gate-halfcache-tile16 / production.
A chooses only after all four B screens finish exactly with unchanged
acceptance and a candidate beats both controls; otherwise it refuses before
launching any owner. Both queues must be planned on a temporary copy before
coordinator admission. Nothing from this CPU task enters a live queue.

Baseline: the local packet97 selection snapshot plus down-tile16. It includes
route-fast, rec-both-plus and E1. The plain gate candidate removes E1; the
half-cache candidate preserves it. Active sealed inputs are `selections/`,
not the old `views/` preparation. See [README](README.md) for exact CPU evidence.

Read `screen-jobs-seal.json`, each view's `screen-seal.json`, and
`evidence/queue-plans104b.json` for completed admission. Missing or mismatched
seals are not permission to launch. `run_screens.py --plan` is CPU only;
execution additionally requires the coordinator's device-window authorization,
fault review, lane admission and fresh outputs. No automatic retries.

Every actual chain startup/host-reference path is tested on CPU, but no record
chain or external submission is qualified. The unchanged v4 wrapper must still
pass all 13 model requests, exact target tokens and per-prompt draft acceptance.
No GPU, service, live queue, settings or frozen packet was changed here.
