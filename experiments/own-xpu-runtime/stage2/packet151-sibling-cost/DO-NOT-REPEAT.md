# Packet151 boundaries

No measured cost yet. Packet132 remains closed pending the upper-bound sibling cost measurement. Cost ≤ 1.952 ms reopens packet132 on packet114 independent text only; higher cost is inconclusive and requires full M=2. Never calibrate on the 12-prompt suite.

- Packet151d: never use direct `q.submit` or reference captures for a prepared
  sibling operation, and never enable sibling work for prefill (`fixture=0`).
  Miniature HOST_ONLY tests miss this device-branch error. Run the saved-rank,
  real-shape preparation regression as well as numerical gates.
  [Evidence and revisit conditions](PREPARATION-CLOSEOUT.md).
