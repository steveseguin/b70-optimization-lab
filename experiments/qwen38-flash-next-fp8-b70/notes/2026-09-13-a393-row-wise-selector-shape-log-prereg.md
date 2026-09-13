# Preregistration: A393 - which tensors enter the row-wise selector branches at max_rows=8 during single-user decode?

## Question

`dc11a3a0a` (= `2a372e86` + the row-wise all-reduce and HC-norm selectors) changed 3 of 8 single-user
oracle outputs at `max_rows=8` (A390 vs A383/A392) although its diff is only the two branches gated on
`1 < shape[0] <= max_rows`. So during single-user decode some all-reduce or HC-norm input has a leading
dimension in 2..8 that is not the token dimension. Which tensors, at which sites?

## Arm

A393: diag head `e12f6adb` (= `dc11a3a0a` + a logging-only module that records every input entering a
row-wise branch once per site/shape/dtype, as a WARNING in the server log). The A392 packet otherwise
(eight-sequence server, selectors at 8, 6 GB floor, port 20010); driver: two exact-2K rows and two full
oracle passes (the logging fires on the first decode steps; the rest is a free repeat of A392's gates on
this head, whose rows are expected to reproduce A390's, i.e. differ from A392's on the same 3 prompts).

## Predictions

At least one logged shape has shape[0] in 2..8 during the single-user rows (the hyper-connection
stream count is 4; a [4, H] or [4, 1, H] input is the expected culprit). The corrected selector then
keys on the token dimension (or requires shape[0] == the scheduler's num_tokens), which restores the
one-row identity and is re-validated by the exact-2K pin before any multi-user re-run.

## Stop rules

Server fails health; rows fail. Timing/logging arm; nothing promoted.
