# Independent target isolation review

Reviewer: Codex subagent `/root/isolation_review`, source review of packet32 then actual packet36 delta.

Every draft mutable buffer, QSA/index cache, route, control, scratch, logits and argmax has a fresh owner allocation. Non-GEMV output binding checks membership in the draft mutable-ID set. Dense outputs come exclusively from the private draft buffer map. The only model-state input is a copy of target streams. Embedding lookup reads a bounded immutable row and never calls target prepare_token or PLE preparation. The resident head is borrowed read-only; CPU streaming has its own head allocation outside the target release map. One owner retains all allocations; the provider is destroyed before owner shutdown.

Only target HALF replies enter emitted tokens. Draft tokens travel in a separate shared control publication, consumed after socket completion, sequence/position/validity/vocabulary checked. Target half_step and rollback arithmetic are unchanged.

Found and fixed: disabled-provider position check; initial stall injection that returned immediately; missing confirmed-token bound. Stall injection now waits cooperatively for 50ms before a declared provider exception. Real owner faults remain fatal and are never disguised as no-guess recovery.

Static review does not replace the CPU state/fixture gates or coordinator device parity windows. No device execution by the reviewer.
