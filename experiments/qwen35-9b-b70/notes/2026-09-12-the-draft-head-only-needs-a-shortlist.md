# The draft head only needs a shortlist: +8-9% at one user, lossless by construction (R294, 2026-09-12)

(Shared note, written in the 4B lane; the 9B rows are the `sl32k`, `slu67k`, `slu92k` and `slbase` arms of
`experiments/qwen35-9b-b70/scripts/run-20260912-qwen35-9b-draft-shortlist-chain.sh`.)

Data: `data/2026-09-12-qwen35-4b-draft-head-shortlist.json` and
`experiments/qwen35-9b-b70/data/2026-09-12-qwen35-9b-draft-head-shortlist.json`; patch
`experiments/qwen38-27b-b70/docker/r294-draft-head-shortlist.py`; shortlists and their builders in
`experiments/qwen38-27b-b70/docker/draft-shortlists/`; chains `scripts/run-20260912-qwen35-4b-draft-shortlist*.sh` and
`experiments/qwen35-9b-b70/scripts/run-20260912-qwen35-9b-draft-shortlist-chain.sh`.

## The idea

Speculative decoding on these lanes drafts three tokens per step with the model's own MTP head, and each drafted
token is an argmax over the full vocabulary projection: 248,320 rows, scored three times a step. The 9B lane measured
that projection at 28% of the decode step even as a draft-only INT4 copy, and closed every knob on it
(`experiments/qwen35-9b-b70/notes/2026-09-10-the-draft-head-knobs-are-closed.md`). The draft only proposes. The
target model verifies every proposed token with its own full FP16 head, greedily, so a draft head that scores only a
*shortlist* of rows cannot change any output: when the true argmax lies outside the shortlist the draft proposes
something else and the target rejects it, which costs one accepted token and nothing more. R294 builds the draft-only
INT4 copy from the shortlisted rows (per tensor-parallel shard) and scatters its logits into a full-width row of
`-inf`, so the proposer's argmax and the TP all-gather see the usual shape.

## The lists

Token frequency over text. `build-shortlist.py` tokenised the lab's own repository (26M tokens: notes, code,
scripts), which uses only 38,655 distinct tokens; `build-shortlist-v2.py` added system documentation, the Python
standard library and the vLLM, Torch and Transformers sources from the image (64M more tokens, 91,754 distinct in
all). Coverage of the 4B's own strict-suite output: the lab-text top 8k / 16k / 32k / all cover 79 / 90 / 98 / 99%;
the unions of everything with the broad corpus' top 32k / 65k / all cover 98.9 / 99.5 / 99.8%. The evaluation
suites were not used to build any list.

## What it measured

One card, depth 3, the published single-user path (`CLASSPAD=0`), strict stage: a fresh MTP0 pair (G1), a
shortlisted depth-3 pair (G2), each against the MTP0 oracle (G3). Every arm below is 12/12 on every gate.

| rows | 4B tok/s | 4B per-position acceptance | 9B tok/s | 9B per-position acceptance |
| ---: | ---: | --- | ---: | --- |
| 8,201 | 161.4 / 161.4 | 0.85 / 0.55 / 0.43 | - | - |
| 16,393 | 179.5 / 179.4 | 0.89 / 0.72 / 0.61 | - | - |
| 32,776 | **193.0 / 193.3** | 0.88 / 0.64 / 0.52 | **124.0 / 124.1** | 0.93 / 0.74 / 0.67 |
| 38,662 | 192.4 / 192.5 | 0.85 / 0.64 / 0.50 | - | - |
| 44,945 | 191.7 / 191.4 | 0.85 / 0.64 / 0.51 | - | - |
| 67,248 | 191.9 / 191.6 | 0.87 / 0.73 / 0.64 | **124.0 / 124.1** | 0.93 / 0.83 / 0.73 |
| 91,754 | 191.2 / 191.1 | 0.92 / 0.82 / 0.72 | 122.2 / 122.2 | 0.93 / 0.82 / 0.72 |
| all 248,320 (control, same image) | 177.6 / 177.3 | 0.92 / 0.81 / 0.71 | 113.5 / 113.5 | 0.92 / 0.79 / 0.71 |

The controls equal the published headlines (177.41 / 177.17 and 113.63 / 112.90), so the image adds nothing on
its own. The gain rises from a loss at 8k rows through +1% at 16k to +9% at 32k, then stays flat to 92k. What
changes along the flat part is how the gain is made: at 32k a 12% acceptance loss is outweighed by a head that
reads an eighth of the rows; at 67k on the 9B, and at 92k on both, acceptance is the control's and the whole gain
is the head reading a quarter to a third of the rows. Per-position acceptance is the server's last logged snapshot
and is noisy; the rates are the measurement.

**Recommendation: the 67,248-row list** (`shortlist-u-v1all-v2top65k.txt`). +8.1% on the 4B, +9.3% on the 9B,
acceptance within noise of the control on both, and the least dependence on the corpora among the lists that keep
it. The 92k list is the fallback for text unlike anything in either corpus (+7.7% with the control's acceptance).
A deployment can rebuild the list from its own traffic with the builders; a list that misses tokens costs
acceptance, never correctness.

## Why it is lossless, twice over

By construction: only the draft's proposals change, and the target's verification is unchanged. And by
measurement: 26 fresh depth-3 servers across the two models, every one 12/12 against its own MTP0 oracle and
against its pair, with the oracle servers themselves 12/12 against each other.

## What it costs and where it stops

Nothing at load time worth noting (the INT4 copy is built from fewer rows). The head still runs once per drafted
token, so the remaining draft cost is the draft *layer* itself; the 32k point on the 4B (193.3) is close to what
a free head would give, which bounds what any further head work can return. The many-user ladder with the 92k
list is in the data file (arm `slu92k-ladders`).
