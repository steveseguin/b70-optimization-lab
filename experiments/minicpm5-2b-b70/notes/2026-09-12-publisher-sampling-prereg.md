# Separate publisher-sampling baseline after failed greedy control

Native-thinking greedy smoke failed at both256 and2048 tokens: no EOS/final
answer, and the longer run repeats an imagined developer instruction. The
original question is unchanged. These are genuine failed quality screens;
the full greedy campaign did not start. No greedy baseline is qualified.

Preregister before execution: a separate publisher Hugging Face sampling track
with seed7429, do_sample=True, temperature1.0, top_p0.95, top_k50 (the default
in the official Transformers usage), min_p0.0, repetition_penalty1.0. Native
thinking, BF16 weights/KV, eager attention, exact prompts, EOS, and every budget
and check are unchanged from the amended campaign. All primary/repeat requests
reset the same seed; preserve every complete output including reasoning.

This is a new baseline generation preset, not a successful optimization of the
failed greedy result. Do not merge their token or speed comparisons. The fixed
suite JSON prompt bytes are reused; this explicit sampling configuration
supersedes their greedy generation fields only for this named track, and the
actual configuration is recorded in every run report. No favorable-seed search
or repetition-penalty adjustment is permitted in this campaign.

The same cached/uncached sampling uses identical seeded draws and must match
the first8 generated IDs; teacher-forced cached/full top1 comparisons remain
diagnostic, and argmax must not be compared to a sampled token as though
sampling were greedy. All usual fresh-process, same-process, numeric/structured
quality, context and semantic gates remain. A failed gate stays failed.
