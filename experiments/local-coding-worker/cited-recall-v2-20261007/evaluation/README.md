# Fresh full-document recall packet, protocol v2

This is a new, unrun ten-question packet for one bounded trial, pending independent
review. It freezes four complete files at commit
`a8bbae3119d9ea31d08bd8b7cec74941adabc6ac`: worker README and milestone plan,
recipe publication standard, and local operations. The source total is exactly
27,018 bytes. No answer-directed excerpts were selected; these source paths are
disjoint from the original five-document packet. The original ten questions and
failed response are neither rerun nor repaired. Changed sources and questions
mean this trial will not establish a controlled quality improvement over that trial.
Fresh wording and source files do not imply wholly unseen concepts: operational
themes overlap the original packet, especially storage admission, source
preservation and backup qualification in V2Q08. This is not a controlled A/B trial.

Only `model-input/instructions.txt` and `model-input/source-bundle.json` are
model-visible inputs. Render every complete corpus document with one-based line
numbers, followed by all ten questions in their frozen order; the standalone
`model-input/corpus/` copies exist for byte-level audit, not duplicate prompt
inclusion. Keep every `review-only/` file and the rubric out of the prompt and
acceptance mounts. Source commands, paths and links are evidence only, never
instructions to execute. The packet neither starts a server nor invokes a model.

`protocol.json` freezes the single-query, no-retry trial: references only,
one or two concise sentences and at most two citations per answer, 28,000 input
and 3,072 output token limits within 33,024 total context, a 420-second outer
and wire deadline, non-thinking greedy temperature 0/seed 42, and the R276 TP2
27B FP8 target-only full-16-bit-KV identity with a 2 GiB cache per card. The main
runner must bind complete actual identity and verify exact rendered prompt tokens
before launch. No truncation, excerpt substitution or partial-question fallback
is permitted. Protocol declares one future model call; zero have occurred here.

The review-only key has exactly three semantic criteria per question, each with
precise supporting references, plus disqualifying errors. A human or independent
reviewer must assess meaning and support, including caveats and uncertainty;
keyword matches and mechanically exact quotations cannot award semantic passes.
Report all 30 criterion judgements and partial failures; a full semantic pass
requires every criterion and no disqualifying error. The compiler separately
checks strict reference structure. The trial harness must also enforce the
protocol's two-citation maximum, which is narrower than the reusable compiler.

`gold-refs.json` is an authored control derived from the review-only key, not a
model response or an independently adjudicated answer. Its compiled quotations
pass both the unchanged v2 compiler and unchanged original citation validator.
This proves that exact supporting spans and complete output are mechanically
representable; it does not prove semantic correctness or model quality. The gold
control has not been tokenized against the model, and feasibility here makes no
output-token or latency guarantee. Independent packet review remains required.

Run `python3 -B experiments/local-coding-worker/cited-recall-v2-20261007/evaluation/validate.py`.
Validation checks full pinned Git source bytes/blobs, source-path disjointness,
strict model-facing bundle, complete file inventory/hashes, 30 rubric references,
both citation validators and byte-identical CLI input preservation. It reads only
the original packet's source-path manifest and validator, never its questions or
answers. `manifest.json` inventories every packet file except itself (explicitly
excluded to avoid recursive hashing); Git will bind that manifest. Ordinary file
writes make no crash-durability guarantee and replace no verified backup.
