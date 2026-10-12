# Packet 32: do not repeat

| Rejected approach | Why | Revisit condition |
| --- | --- | --- |
| Cross-card SYCL dependencies/shared context | Leading unproven packet16 fault suspect; unnecessary here. | Separate explicit evidence and owner scope. |
| Swap a buffer map but retain old prepared bindings | Kernels would keep writing the wrong bank. | Both prepared maps move with bank selection. |
| Treat PLE hash as output-only history write | It mutates through its input pointer. | Explicit 16-byte checkpoint/restore or rewritten kernel with a new gate. |
| Two-layer mini split used as complete rollback gate | Rank0 lacks PLE/QSA. | Four-layer split with all state classes on rank0. |
| Uninitialized spare state | Host adapter reads output storage before overwrite. | Initialize once before any half. |
| Check all ranks alive while sending normal FINISH | First clean exit can race the second send. | Expected-exit state installed before sending. |
| Clear sticky errors on a miss | A hardware/operator error is not a wrong token guess. | Never; abort both. |
| Scripted oracle guesses as a speed result | It is a diagnostic ceiling. | Never; use a real provider. |
| CPU resident full-weight ranks | Exceeds preparation memory budget. | Host gates stream layers; native windows admit per-rank residency. |
| Treat command interval overlap as synchronized GPU timestamps | Device clocks are independent. | Report host overlap and local profiling separately. |

Earlier packet29 arithmetic/kernel caveats remain in its sealed packet, including
the unqualified nonfinite expert-down diagnostic. No failure is relabelled exact.
