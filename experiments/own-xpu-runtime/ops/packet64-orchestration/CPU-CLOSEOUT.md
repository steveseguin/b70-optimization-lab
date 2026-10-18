# Packet64 orchestration CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Can the coordinator select packet64 from the two d7 screen lanes, fast-reseal
that selection, run the frozen chain, and schedule two lane-B companions
without bypassing the sealed timing holds? October 17, 2026; CPU preparation
on steve-b70s. Existing packet64 weights, arithmetic and full BF16 KV remain
the runtime identity; no model was loaded here.

## Outcome

Prepared and tested with mocks. Same-lane selection, exactness fallback,
mandatory precheck order, separate unit construction, failure exits and
one-at-a-time companions are covered. No measured GPU result or record claim.

## What worked

The existing sealed companion already implements the required reservation
and drain protocol. Reusing that entry avoids an external hold-check race or
a nested lane lock. Its 34 CPU protocol/drain/adapter tests passed. The
orchestration's actual shell entry completed a fully mocked chain and both
companions; [the log](dry-run.log) records their sequence and explicit exit.

## What failed or remains uncertain

Injected quality failures, missing/tampered receipts, invalid controls, a new
fault and failed chain prechecks refuse adoption or launch as appropriate.
A missing/invalid companion preflight skips that optional work. Native
overlap, available host memory during overlap, and drain/watchdog interaction
remain device-qualified only by a future coordinator run. No frozen code was
changed to relax them.

## Evidence and patches

[Source and coordinator command](README.md), [tests](test_orchestrate.py),
[test output](tests.log), [validation](validation.json),
[synthetic full dry run](dry-run.log). All new code is in this directory;
the frozen packet and screen trees were preserved.

## When to revisit

The coordinator starts the documented unit after this preparation. Fresh
d7 evidence determines the choice; the existing full chain determines device
quality and speed. A failed attempt needs investigation and fresh authorized
outputs, never an automatic rerun or marker deletion.
