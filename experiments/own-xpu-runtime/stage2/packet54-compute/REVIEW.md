# Packet54 independent review

Three subagents independently developed recurrence, route and HC/FFN source
analysis and kernels. Route reviewed recurrence/HC arithmetic and the root
benchmark, parser, wrappers and integration map. Recurrence reviewed HC tests
and the actual production M2 state alias. Root remains responsible for gates.

Confirmed from source: original subgroup/upper trees, BF16 state reload,
unchanged deterministic math, route normalized ties and four-pass scratch,
full capture/event counts, correct packet49c dispatch and separate 25/40 µs
bars. Admission concerns are carried into INTEGRATION.md: preserve production
shape/lifetime/alias checks and adapt to one engine type tree.

Corrections made during review:

- Failed teardown must hold the owner for the supervisor; never silently exit.
- PF_EXITING uses stat field9 and still rejects missing RSS for a live task.
- The bank receipt itself is hash-bound, not just copied numeric constants.
- Zero-saving ties prefer the production control.
- HC guard tests compare sentinel scratch as well as output/error.
- A NaN-payload failure requires actual compiled-production parity, not merely
  a handwritten algebraically identical leaf. The exceptional side gate is
  distinct from cross-backend finite CPU-reference comparisons.

CPU evidence and device compilation are prerequisite checks, not device
qualification or proof of a speed gain. E1/E2 and T1/T2 remain required.

Actual compiled-production gates overruled helper-only success: FFN vector
combine and both norm proposals failed NaN-payload parity and were removed
from eligibility. Their source and failure receipts remain. The final mix-only
arm passed finite and exceptional production checks. A final recurrence-agent
review confirmed exactly five eligible arms, correct per-arm M2 BF16 state
carry, production norm/inject dispatch, zero FFN credit, and exceptional mix
receipt binding. Closed-arm helper tests are archived separately so they
cannot qualify or block unrelated eligible kernels.
