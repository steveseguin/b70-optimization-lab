# Packet 129 draft acceptance: draft format is not the limit, closed (2026-10-18)

Lane B, `p129-acceptance-B-a` 13:32–14:03 UTC, acceptance-only diagnostic (production draft's guesses used; candidate draft evaluated side by side; target verifies every token; exact). Primary decision on calibration text independent of the 12-prompt suite (packet 114's preregistered non-benchmark corpus).

Candidate (draft experts decoded faithfully from the publisher's FP8 instead of the production INT8 re-quantisation): **975 → 976 matched of 1,230 (+0.08 points)** vs the +1.5-point kill gate. Closed. DO-NOT-REPEAT: draft-format / draft-quantisation variants change acceptance by about ±0.1 point; acceptance is limited by the MTP head itself, not its weight format.

Process note (hourly review 24b): the primary gate was decided at ~13:47, but the 12-prompt secondary pass ran another ~15 min and kept the packet124c chain's whole-host W2m window waiting (lane A idle 13:37–14:03). Future diagnostics stop at the primary verdict, and lane-B jobs do not start within reach of a running chain's next whole-host window.
