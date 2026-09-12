# Initial native-thinking smoke and fixed larger-budget follow-up

Run1 at e3dde3434 loaded original BF16 weights successfully; actual cache tensors
were BF16, device peak allocation5,048,346,112 bytes. The smoke generated256
tokens in14.002 seconds without EOS or a final answer. It spent the budget
reasoning about an imagined developer instruction, so this is not a correctness
pass. No realistic/quality suite was started. Four-card pre/postflight passed.

Preserve `/home/steve/minicpm5-baseline-20260912/{guard-run1,campaign-run1}`.
Before another execution, preregister a2048-token smoke cap, matching the fixed
objective-quality budget. This changes only the preliminary smoke cap: same
prompt, model bytes, runtime, native thinking, greedy decoding, and all planned
suite settings. Do not call the prior256-token output a successful answer. If
the longer smoke fails, stop before the full campaign and investigate; do not
silently relax the answer checker or disable native reasoning.
