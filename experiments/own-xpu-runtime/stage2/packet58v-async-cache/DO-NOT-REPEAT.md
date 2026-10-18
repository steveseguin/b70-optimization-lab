# Packet58v boundaries

| Arm or interpretation | Outcome | Revisit condition |
| --- | --- | --- |
| Temporary queue planning proves device startup works | Refuted by inherited 58r unit gate; packet58vb replays the real queue and all six native boundaries | Repeat the real-entry gate whenever startup or lanequeue naming changes; [closeout](packet58vb-closeout.md) |
| Current serial cache span is already negligible | Refuted by 58p/58r/58t receipts: 6.84–7.22 ms in metric windows | A newly measured span below 1.5 ms/token |
| Separate copy queue alone proves overlap | False: the old owner chain and compute barrier serialized it | Small real-device async smoke, then matched bracket |
| CPU mocks prove native queue dependencies | False; tests prove the protocol/wiring only | Required 12 × 64 device smoke before the larger bracket |
| Publish a fill immediately when it completes mid-position | Refused; current kernels own their table snapshot | Publish only at a later drained boundary |
| Reuse a pending slot again | Refused by the one-transaction protocol | Previous transaction completed and published |
| Call the delayed pipeline a zero-lag cache or predict its hit rate | Unsupported | Actual fill/hit/position receipts |

Keep all 58c/58d lifetime and admission boundaries, and 58h/58i/58n/58r/58t
closed levers. No MTP, frequency prefetch, route/recurrence retuning, resident
lookup experiment, compressed KV or altered arithmetic is reopened.

Do not alter a frozen parent, screen tree or live ops queue. Do not reduce
host reserve or the measured-policy allowance from a favorable new sample.
Do not call either proposal a record run, an independent repeat or a strict
512-token gate. Both proposals remain unqueued by this CPU preparation.

[CPU closeout](CPU-PREPARATION-CLOSEOUT.md).
