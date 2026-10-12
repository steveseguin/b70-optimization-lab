# Independent emitted-token review

The suite subagent reviewed the native controller and draft code, independently
of their authors. No token-authority violation was found in this source snapshot.
The exact source hashes are retained in `review-token-authority.json`.

`native38::run` appends only the result of the confirmed rank-1 target HALF.
The native MTP publication is checked for valid flag, error, expected position,
mailbox sequence and token range. Its only use is as a speculative rank-0 input.
The unchanged target token decides acceptance. A miss restores the banked state,
PLE history and position, then recomputes with that token. Rank 1 rejects a
speculative HALF. An early EOS undoes a pending rank-0 guess before returning.
The Python path has the same token authority; neither path emits provider output.

Draft kernels bind outputs from the private draft buffer map. Nonlinear binding
checks require mutable draft allocation ownership. GEMV outputs, merged hidden
state, controls, attention scratch and head scratch also come from that map.
The shared target output-head weights and RoPE are read dependencies only. The
hidden-state copy direction is target streams to draft merge.hidden. Embedding
lookup reads a weight row; it does not call target token preparation or mutate
its PLE history. Prepared commands preserve those bindings. Reset updates bytes
in place and never frees the owner's target captures.

This source review complements the executable mini-model equivalence and
prepared-draft gates. It is not a substitute for the real model windows on the
cards; no device executed during this review.
