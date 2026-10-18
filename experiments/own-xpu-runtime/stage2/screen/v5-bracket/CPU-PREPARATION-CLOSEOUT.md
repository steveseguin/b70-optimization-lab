# Packet98 CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Can one v5 TP2 rank pair switch packet84 control and packet91 route-fast plus
rec-both-plus without reloading target/draft weights or retaining response state?
October 18 CPU-only preparation, packet82b kernel objects, packet49 arithmetic,
full BF16 KV, 24/24 target split and rank1 draft. Future device lane is B.

## Outcome

CPU native builds, full-shape startup/reset, poisoned miniature byte checks,
fresh real-IPC token parity and wrapper mock checks pass. Device correctness,
A/A timing equality and actual model-load wall-time savings remain unmeasured.
Two and five views are separate proposed jobs. No public speed claim is made.

## What worked

A quiescent native switch rebuilds both bank captures without device-owner
teardown. Locked weight uploads and loaded-arena hashes protect the shared load.
Memory refusal happens before lease creation; prelaunch races release the marker.
Real reset-byte checks cover all mutable allocations and spare banks. Fresh CPU
rank-message tests cover the actual command13 path, not just a Python plan.

## What failed or remains uncertain

Initial CPU preparation caught an unqualified hash namespace, an inherited
entry object that duplicated the fixture main, a test include search path that
selected the parent raw source, and an unregistered miniature storage context.
They were fixed before the final gates. No GPU fault occurred. Full-size tests
mock payload/backend data; miniature parity is not full-model parity. The
coordinator must run the small A/A smoke before any mixed-view bracket.
No speed verdict is valid from these CPU fixtures. Device wall savings are pending.

## Evidence and patches

[Native build](evidence/build.json), [full-shape startup](evidence/full-shape.json),
[byte reset](evidence/reset-bytes.json), [real CPU IPC](evidence/protocol.json),
[bracket tests](evidence/bracket-tests.log), [native changes](native_source.py),
[wrapper](screen.py), [state machine](bracket.py), [receipt adapter](compare.py).
Generated binaries stay under ignored `build/`; restore instructions and parent
object identities are in [README](README.md) and the build receipt.

## When to revisit

After the authorized A/A smoke passes exactness and the 3% control drift bound,
run the five-view lane-B candidate bracket. Extend the switch whitelist only
with new startup, layout and reset proof. Layout-changing choices use v4/reload.
