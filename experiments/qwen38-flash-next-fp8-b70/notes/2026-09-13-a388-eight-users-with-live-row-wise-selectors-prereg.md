# Preregistration: A388 - eight users on the MTP0 line with the row-wise selectors actually present

## Question

A383 showed 2-8 concurrent sequences are not output-identical to single-user decode on the MTP0 head
`2a372e86`, and a code search then showed that head carries neither `VLLM_XPU_ROWWISE_ALLREDUCE_MAX_ROWS`
nor `VLLM_XPU_ROWWISE_HC_NORM_MAX_ROWS` (both were added in the MTP1 lineage), so the tensor-parallel
all-reduce ran batched over M rows, the path A104/A105 showed is not bit-equal to per-row reduction. With
the selectors live at 8 rows, are the concurrent outputs identical to the single-user outputs, and at
what aggregate rate?

## Arm

A388: the A383 packet on a new MTP0 candidate head `dc11a3a0a` = `2a372e86` + the two selector commits
cherry-picked (`8ca2cbc28` all-reduce, `1b2a17c1e` HC-norm; branch `q38-mtp0-rowwise`; the envs.py
conflict resolved by taking only the row-wise declaration, the three serial-spec switches of the MTP1
lineage have no code on this head). Everything else A383: `max_num_seqs=8`, KV 1,412,136,960, capture
sizes [1, 2, 4, 8], never-hit + max-count-2 placement, 8 GB host floor, selectors at 8; port 20005;
the same identity-gated concurrency oracle, two repeats. Queued after A387.

## Predictions

- At one user the arithmetic is unchanged (the selectors only act on 2..8-row inputs), so the c=1 oracle
  rows must reproduce A383's c=1 outputs; if they do not, the head is wrong and the arm stops.
- If the batched all-reduce was the only batch-variant term, 28/28 concurrent completions match and the
  "Many users" cell becomes lossless at ~82 tok/s (the selectors cost little: 1.5 ms at two rows). If
  matches improve but stay partial, the remaining term is the oneDNN dense-projection primitive choice
  per M (router/LM-head logits) or the HC gate-mix mean, which the HC-norm selector does not cover, and
  the next arm pins those.

## Stop rules

Server fails health; c=1 rows differ from A383's c=1; oracle identity failure is recorded as before.
