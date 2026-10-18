# Packet84 coordinator handoff

Preparation only. Do not launch a chain from this note. The one-shot helper
in ../../ops/packet84-orchestration/orchestrate.py writes ready.json containing
its exact print-only systemd command after all prechecks pass. verify_ready.py
checks the boot, source/result hashes, selected seal and unused chain output.

The fresh chain has11 windows: K0, K1a, K1b, K2, W0p, KD, W2m, WS, WSs,
WS128x, WS128. Each gap is90 seconds. The pinned shared v4 lane admission,
whole-host timing reservation, graceful teardown and release-before-report
remain. No automatic retry, restart or return to a resident service.

The four placements are explicit in bundle_selection.py. Rank0 placement0 is
24/24, never historical22/26. Rank1 ordered cleanup is independent of draft
placement. No target arithmetic, weights, oracle, cache precision or prompt
reuse change. Component screening is diagnostic; the composed chain must
establish its own exactness and speed.

Submission/resume entry remains submission_cli.py; it rejects another packet's
binary/source identity. Fast reseal materializes the selected CPU-proven view
without compilation and refuses after a chain starts. New draft heads require
placement1. Every selection runs all11 window plans before readiness.
