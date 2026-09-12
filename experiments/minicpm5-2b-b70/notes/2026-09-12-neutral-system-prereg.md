# Neutral system-message setup trial

Run3 publisher sampling passed the arithmetic smoke and five of six objective
checks. `ordered-dedup` produced the correct array wrapped in Python fences,
failing the explicit JSON-only requirement. This is a model-formatting failure,
not a passing canary. The primary reviewer stopped the owned campaign after
capturing the failure; no fresh-process baseline or qualification was completed.
Four-card postflight passed after controlled cancellation. Preserve all partial
run3 rows and the prior input identity; no result is overwritten.

Before the next execution, fix a separate chat preset with one standard
system message: **You are a helpful assistant.** No task-specific hints,
rewritten user prompts, seed search, output repair, grammar constraint, or
checker relaxation. Original weights, BF16 KV, eager runtime, native thinking,
publisher sampling seed7429 and all budgets remain unchanged. The system
message and resulting complete input IDs are part of the new baseline identity.

Run4 stages: arithmetic smoke, then a fresh-process six-canary quality pilot.
Only if all six exact checks pass, start fresh processes A/B for the full
previously declared baseline campaign. The pilot is excluded from timing;
realistic prompts are still unique first requests within each A/B process.
This trial determines whether an ordinary chat setup resolves the failure;
it is not a claim that the original no-system preset was qualified or optimized.
