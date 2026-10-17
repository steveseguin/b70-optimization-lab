# Packet56 retained decisions

- Do not choose or change N from benchmark prompts, outputs, acceptance or timing.
- Do not crop the target head, change vocabulary metadata or allocate a second head.
- Do not change the per-row reduction or use the suffix logits in draft argmax.
- Do not reuse the parent's full-head draft proposal as the prefix proposal oracle.
  KD uses the unchanged target captures and recomputes only its draft reference.
- Do not label synthetic CPU or K-window passes full-model quality or speed evidence.
- Do not edit the parent packets or the shared submission helper while49d runs.
- Keep the [parent's negative results](../packet49d-round3/DO-NOT-REPEAT.md).
