# Source-backed lab-memory questions

Ten questions use five complete documents frozen at commit
`76f3ebd23f3f9b378e6088678967addd0b617951`. They test decisions, changing evidence,
exact artifact retrieval, contradictions and appropriate uncertainty.
No model has answered them in this evaluation.

Give the answering model only [questions.json](questions.json) and the five
`corpus/*.txt` documents it lists. Keep [answer-key.json](answer-key.json),
validation receipts and repository history out of its input. The
[protocol](protocol.json) specifies isolation and grading; this packet does not
itself implement a model runner or isolated mount.

```bash
python3 experiments/local-coding-worker/evaluation-20261007/memory/validate.py --self-test
python3 experiments/local-coding-worker/evaluation-20261007/memory/validate.py --responses /path/to/answers.json
```

Validation checks frozen source bytes, hashes, IDs and exact quoted line ranges.
It never infers that an answer is correct because it contains certain words.
An independent reviewer must apply the thirty-criterion rubric and the listed
disqualifying errors. Report citation validity separately from factual and
semantic correctness. Curated document recall is not a long-context capacity
measurement or proof of generalization to unseen research.
