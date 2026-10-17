# Packet56x CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Can packet56w's host polling sleep be removed without changing its kernels,
arithmetic or controller semantics? Two host policies, one common object build,
on steve-b70s, October 17. Target remains the packet56 quantized compressed
Flash-Next IQ3 lane and packet49 oracle; no model/device execution here.

## Outcome

CPU preparation passed for both variants: 1,123 controller cases, five mailbox
fault checks, seven wait checks, 765 identical fixture bytes against packet56,
separate seals and screen v1 CPU plans. No device speed or exactness verdict.

## What worked

A shared deadline-aware polling helper covers device events, controller mailbox
and same-thread draft progress. Two small linked constants choose the policy,
while every kernel object is shared. Each seal rejects the other binary.

## What failed or remains uncertain

The initial configure omitted inherited prototype fixture headers; copying those
unchanged headers fixed it. The first log is retained. Device timing, CPU cost
in the full runtime and exact outputs remain unmeasured. A 20 us requested sleep
can overshoot under scheduler load; pure spinning uses more CPU.

## Evidence and patches

[Wait audit](WAIT-AUDIT.md), [source delta](evidence/source-delta.json),
[patch](evidence/native-waits.patch), [spin fixture](fixture/spin/receipt.json),
[sleep20 fixture](fixture/sleep20/receipt.json),
[spin plan](evidence/screen-plan-spin.json),
[sleep20 plan](evidence/screen-plan-sleep20.json),
[seal rejection checks](evidence/seal-negative-checks.json),
[build/restoration](README.md), [storage](evidence/storage.json).
All CPU logs and receipts remain in this folder; no raw device evidence exists.

## When to revisit

The coordinator runs [both screen commands](WINDOW.md) under fresh admission,
with matched placement/priority and the unchanged packet49 oracle. A promising
screen proceeds to full sealed qualification; the optimization lane stays open.
