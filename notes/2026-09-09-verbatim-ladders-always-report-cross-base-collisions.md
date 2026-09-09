# A verbatim ladder always reports cross-base collisions and is always classified `measured-output-variant`

Found while pre-validating the 4B fragile suite before spending cards on it.
Not fixed here, for the reason in the last section.

## The signal

`bench-openai-concurrency-oracle.py` counts a *cross-base oracle collision* when
one request's output matches an oracle belonging to a different base prompt. It
is a good check: with 64 distinct texts, two of them producing byte-identical
128-token outputs means the identity comparison is not discriminating what it
claims to.

Base identity comes from:

```python
def base_prompt_id(prompt_id: str) -> str:
    return re.sub(r"-c\d+$", "", prompt_id)
```

## Why it misfires under `--verbatim-prompts`

Verbatim expansion exists so a prompt known to sit on a tie keeps its exact text
across slots; it gives each slot a unique id by appending `-s{index:03d}` to the
suite's own prompt id. A fragile suite's prompt ids are already the expanded ids
of a previous run, so a slot ends up named `cache-c056-s016`.

That does not end in `-c\d+`, so the regex strips nothing and every slot is its
own base. The four verbatim copies of one prompt then produce identical outputs
under four different "bases", and every one is counted as a collision — by
construction, on a healthy run.

The harness docstring says the opposite:

> Slots then repeat texts, which the cross-base collision check tolerates because
> repeats share a base id.

They do not share a base id under this regex.

## What it costs

Nothing in the identity numbers. `oracle_exact_count` and `oracle_exact_total`
are computed independently and are correct. What breaks is the derived
`classification`, which requires `cross_base_oracle_collision_count == 0` for
`output-isolation-qualified-shape-variant`, so a verbatim run always lands on
`measured-output-variant` no matter how exact it was.

The 9B's four verbatim fragile campaigns already show this — collision counts of
51 to 64 out of 64 in every batch, all classified `measured-output-variant`:

```
qwen35-9b-w4a16-tp2-fragile-f0   collisions=[63, 64, 63, 64]  measured-output-variant
qwen35-9b-w4a16-tp2-lmhead-L1    collisions=[64, 64, 64, 64]  measured-output-variant
```

So this has been happening since the fragile-prompt method was introduced, and
tonight's `g1`/`g2`/`g3` arms will show it too. Read `oracle_exact_count`, not
`classification`, on any verbatim run.

## Why it is not fixed here

`scripts/bench-openai-concurrency-oracle.py` is pinned by SHA256 in
`experiments/qwen38-27b-b70/data/2026-09-02-...-r147-prereg.json` and is a listed
dependency of five packages including `qwen35-4b-w4a16-b70`. Editing shared
pinned tooling in place is the failure recorded in
`2026-09-08-a-good-tooling-change-broke-a-record-gate.md`, where four good
changes left the Laguna record gate silently unrunnable for two weeks.

The one-line fix is `re.sub(r"(-c\d+)?(-s\d+)?$", "", prompt_id)` or equivalent,
and it belongs with a decision about re-pinning the r147 preregistration and the
package dependencies — the owner's call, not a side effect of a 4B campaign.
