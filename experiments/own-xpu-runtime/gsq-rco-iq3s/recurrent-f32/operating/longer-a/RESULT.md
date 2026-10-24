# First longer request diverges at output token 71

The corrected5926 engine completed512 target-only tokens for the first fixed
incident-retrospective prompt. Its first70 output IDs match the independent CPU
reference. At zero-based index70 it chooses token220 (a space), whereas the
reference chooses264 (" a"). The conditional input is identical at that point:
87 original input IDs plus70 generated IDs, totaling157 tokens. The reference
ranks these candidates first/second with a top-two log-probability gap of
0.06167030334472656. That is descriptive, not a quality tolerance.

The runner retained the complete failed request before stopping the remaining
two requests. Independent closed metadata readback classifies this as a safely
closed numerical mismatch: both intended devices observed, no new fault,
protected vision unchanged, both owners exited and target descriptors drained,
zero retries, hard kills or service changes. The original terminal remains
failed. No full-state qualification or throughput claim is made.

The failed request has no guaranteed final target dump. Even an end-of-request
capture would use a divergent prefix, so it would not localize the first
prediction difference. Next: replay exactly the157 shared IDs with one output
using the unchanged5926 binary, require it to reproduce native220, and retain
its final logits. A separate head observation may then isolate the final BF16
rounding boundary without silently changing the target behavior.

The complete native text, including its invented incident details and truncated
ending, is retained without editing. The prompt asks for a draft retrospective;
these details are not verified real-world incident facts. Both reference and
native outputs reach the registered cap. No broad quality judgment is inferred
from this single trajectory difference.

[Closed metadata review](evidence/closed-metadata-review.json),
[raw-token/text readback](evidence/native-full-text.json),
[registered plan](plan.json), [source review](evidence/independent-review.json),
and [first-difference observation](evidence/root-first-divergence.json).
