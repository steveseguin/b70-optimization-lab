# Alleged first-token failure — closeout

<!-- campaign-closeout -->

## Question and identity

Does the October 11 card-3 Packet 13 run produce the reported wrong answer
on the 87-token incident-retrospective prompt? Unsloth UD-IQ3_XXS is the
separate quantized compressed model; arithmetic is
`iq3-p13-r234-sg32-split4-bf16-v1`. This investigation executes only CPU
builds and observes the existing native window read-only.

## Outcome

The alleged generated sequence is exactly the prompt prefix. No wrong native
prediction is established. CPU checks and retained layer fixtures support
the later exact comparison, while native agreement remains pending. No
production arithmetic change, lossless qualification or speed claim results.

## What worked

Binding log fields to source code and matching all input IDs exposed the
reporting error. The unmodified host CLI repeats layer 0 exactly; two fresh
prefix checks agree. Fixture reporting distinguishes incomplete coverage from
success and distinguishes a first observed mismatch from a localized first
divergent layer.

## What failed or remains uncertain

The requested device/operator localization lacks the final-prompt native
fixtures at the audit boundary. Old BLAS-order layer-0 hashes still differ;
their small numerical differences are not an exactness pass and do not prove
that every difference comes from GEMV order. Full native identity, quality
and fresh-process repeat gates remain open.

## Evidence and patches

[Investigation and text](../../../../../notes/2026-10-11-first-token-correctness.md),
[CPU build/reproduction and retained fixtures](README.md),
[input snapshot](input-audit.json), [original integration tests](cpu-tests.json),
[reporting tests](reporting-tests.json), [BLAS diagnostic](blas-layer0.json).
The only code changes are diagnostic tools; exact measured harness source is
preserved alongside its build receipt. Scratch is removed after retention.

## When to revisit

Compare the existing native run's completed step-1 files with the retained
CPU files as soon as they exist. A genuine first mismatch justifies a
separately admitted per-operator device capture; absent files do not justify
a new device launch. The optimization lane remains open.
