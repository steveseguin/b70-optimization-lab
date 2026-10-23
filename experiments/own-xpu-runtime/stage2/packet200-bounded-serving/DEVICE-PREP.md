# Packet200 sixteen-turn serving qualification: preparation

## Question and identity

Can one bounded native owner serve a complete local chat exercise, preserve
the tested model's exact outputs, and close with enough evidence to safely
restore the prior applications? The [frozen coordinator](CPU-CLOSEOUT.md) uses
the p198/p199 baseline ELF, full BF16 state, context4096 and the
21,552,729,600-byte expert cache. It is a serving test, not a cold speed record.

## Outcome

Preparation passes57 CPU checks:10 execution-adapter,30 controller/restore and
17 client checks. The root repeated the adapter sets; the client and adapters
also have independent reviews. All HTTP/native/service operations in these
tests are intercepted. No model owner, endpoint request, application transition
or operational fault capture is represented by this result.

## What worked

The additive adapters require a separate root-authored source/plan manifest
before any application stop or queue mutation. One native unit and one CPU
client unit have fixed identities and nonrestarting, process-only graceful
shutdown properties. The controller preserves both pause files and empty
queues, checks the full forecast before stopping applications and again after
drain, and rechecks the exact plan before launching the worker.

The client first checks health/model routes and one expected400 sampling
refusal. It then submits16 sequential valid requests, capped at1728 output
tokens in total. Five complete outputs must match the retained p198 A/B
oracles; resumed chat must match the fresh version of the same conversation.
Edited history must select fresh processing. Eight additional short prompts
cover formatting, summarization, translation, JSON, code, arithmetic, supplied
history and Unicode; they have no prerecorded semantic-quality oracle.

Every response is checked against the actual per-request native result and
exact consumed `input.tokens`, including HTTP content, finish reason and
usage. An unexpected result halts the client and writes the fixed incident
latch without retry. A client receipt alone is insufficient: both client and
worker must exit successfully, with matching manifest/vector/listener
provenance, all16 request/control dispositions and independent physical drain,
before restoration. Direct invocation of the restore adapter enforces the same
join and exclusive attempt markers.

## What failed or remains uncertain

Review fixed a race where restoration could precede the client's final oracle
check. It also tightened staging identity, full admission before application
shutdown, direct restore admission and failure evidence. Client review added
exact consumed-prompt checks and preserved the original exception when STOP,
evidence, connection close or writer close also fails. Prior reviewed
candidates and test-fixture failures remain under `lineage/`.

The frozen native/storage forecast is768MiB, with another1MiB reserved for
bounded client evidence, above the27GB root floor. The forecast is not a hard
bound on external driver/native writers. Passive monitoring cannot guarantee
the floor against an already-running write burst. Extra local headroom is
being prepared through separately verified archival of closed p199 states.

The first session retains the conservative launch-time idle origin. Model
loading consumes part of the initial240-second allowance, so the controller
starts its single client promptly after the fresh listener event. No retry or
automatic server cycle is allowed if admission expires. The optional mapped
clock adjustment is not used for this first qualification.

## Evidence and patches

- [57-check root gate](evidence/device-cpu-gates.json),
  [adapter receipt](evidence/adapter-cpu-tests.json),
  [client receipt](evidence/client-cpu-tests.json).
- [Independent adapter review](evidence/independent-adapter-review.json),
  [independent interface review](../../ops/packet200-window/independent-adapter-interface-review.json),
  [independent client review](evidence/independent-client-review.json).
- [Fixed vectors](client-vectors.json), [client](client_pilot.py),
  [client tests](test_client_pilot.py), [entry adapter](run.py),
  [controller and restoration contract](../../ops/packet200-window/DRIVER.md).

The native engine, previously sealed profiles, worker and original contract
remain unchanged. Execution adapters and the qualification client are additive.

## When to revisit

Bind the final source closure, independent receipts and unchanged CPU plan into
the root admission manifest. Complete the storage operation and fresh live
checks before one device window. After a successful joined qualification and
drain, restore the three prior applications once and independently audit both
the native/client results and restoration. Preserve any failure and halt new
requests; no automatic retry is part of this packet.
