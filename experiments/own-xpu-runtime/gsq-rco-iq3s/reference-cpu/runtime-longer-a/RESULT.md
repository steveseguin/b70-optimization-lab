# Three longer CPU reference outputs retained

One CPU-only owner completed the original incident-retrospective, code-review,
and customer-email prompts, with fresh prompt evaluation for each. The first
two reached the 512-token cap; the email ended naturally after 334 tokens,
including EOS. All 1,358 output IDs and all 1,358 probability rows were retained.
The independent closed readback passed; every reported chosen token is a greedy
argmax. Actual logs confirm BF16 attention KV and F32 recurrent/history state.
The owner exited with code 0 after one graceful signal.

These are reference outputs, not a broad quality endorsement. The full incident
text invents dates, impact and financial details; it and the code review are
truncated at the registered cap. The email adds operational details beyond its
prompt. All text is retained unchanged in the review. The next comparison uses
exact raw tokens and natural stopping, with no selection or response editing.
After the first native/reference divergence, later free-running logits would
have different conditional prefixes and cannot measure aligned numerical error.

[Closed readback](evidence/closed-readback-review.json) binds the raw external
artifacts, plan, source, prompts, probabilities, text, dtype and owner closure.
No new model payload hash or GPU execution is claimed by this readback.
