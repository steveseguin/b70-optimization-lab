Card sharing between six-card gates and one-card helper benches (2026-11-11)
- A six-card gate creates /home/steve/dsv41-work/six.active at its start (removed on exit), then waits until
  /home/steve/dsv41-work/locks/ is empty before its first run.
- A helper may start a one-card bench only when six.active does not exist. It first creates
  /home/steve/dsv41-work/locks/<helper>-card<N> (touch), runs the bench (short: under ~3 minutes, via systemd-run --user,
  ONEAPI_DEVICE_SELECTOR=level_zero:<N>), then removes its lock file. Re-check six.active before every bench.
- Also skip if `pgrep -a own_run_v41` shows a process (a run that predates this protocol).
- Card numbers: helper A (routed experts) card 3, helper B (engram gate / small kernels) card 4,
  the prompt-rows helper its current card. One SYCL context per card; never two benches on one card.
- No CPU builds (icpx) while six.active exists: they disturb the gate's timing.
