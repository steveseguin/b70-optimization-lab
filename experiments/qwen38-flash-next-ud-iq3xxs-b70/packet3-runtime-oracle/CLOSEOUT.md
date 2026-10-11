# IQ3 packet 3 arithmetic rebase closeout

## Question and identity

Question: can a bounded CPU oracle reproduce the runtime's declared arithmetic
identity, rather than gate the device against a BLAS library's reduction order?

Identity: Unsloth UD-IQ3_XXS revision
`766911a6b7369840a91dbcd95f9f997acaab6cd6`, arithmetic identity v1
`iq3-p13-r234-sg32-split4-bf16-v1`; exact source map in
[arithmetic.json](arithmetic.json), build and CPU library identities in
[build-receipt.json](build-receipt.json) and [environment.json](environment.json).

## What worked

Reuse the shared packed decoders, measured dispatch and per-row
reduction trees. The CPU producer also reuses the nonlinear core, including
PLE's BF16 pre-SiLU boundary and scalar libm. Parallel output rows change only
scheduling. The Python adapter remains available for isolated matmul tests;
replacing only Python matmul is insufficient for full hidden-state equality.

## Outcome

[Independent operator checks](proof.json), [Python adapter checks](adapter-proof.json)
and [two fresh real-layer checks](evidence/real-layer/proof.json) pass.
Both serial and parallel layer-0 outputs equal the saved integrated CPU
reference byte for byte for all 87 prompt tokens' final hidden state.
The [main run](runs/arithmetic-v1-parallel-20261011/receipt.json) and README
record 87 input tokens, 64 generated tokens, 384 layer fixtures, 9.16685 seconds
per decode token and the informational output comparisons.

## What failed or remains uncertain

Negative/partial work: the [serial pilot](runs/arithmetic-v1-20261011/receipt.json)
was stopped cooperatively during prefill once the independent-row parallel
adapter passed. No token or full-prompt quality result is claimed for it.
Its original numeric source is retained and its logs remain evidence. The
existing-output refusal test caught and fixed an error-path overwrite before
the parallel run; [preservation test](preservation-test.json) confirms the fix.

Limits: a matching CPU header and real layer are not a device pass. Native
transcendental agreement, all covered token/layer comparisons, fresh-process
device repeats and the other eleven prompts remain separate gates. The
arithmetic rebase deliberately does not require old BLAS hidden hashes or
llama.cpp tokens to match; their divergences and available margins are recorded
as information, including the effect of the nonlinear/PLE rebase.

## Evidence and patches

The [C ABI](matmul.cpp), [Python adapter](linear.py), [CPU producer](oracle.cpp)
and [build overlay](build.py) retain the implementation. The
[validated run](runs/arithmetic-v1-parallel-20261011/validation.json),
[BLAS margins](runs/arithmetic-v1-parallel-20261011/blas-comparison.json) and
[llama.cpp comparison](runs/arithmetic-v1-parallel-20261011/baseline-comparison.json)
retain results. [Retention](RETENTION.md) explains the logs and restoration.

## When to revisit

Revisit if the decoder, dispatch, tree, rounding, nonlinear library identity or
model bytes change. Bump the arithmetic identity and regenerate fixtures;
never edit old hashes into agreement. This bounded CPU packet closes its
implementation task, not the optimization lane.
