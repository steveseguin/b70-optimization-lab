# Context-sized RoPE allocations (2026-10-27)

Engine `6280724f7c75bf6eb00c6b380805b225865b192c37fd9d717a3077ee091825ee` sizes both BF16 and F32 RoPE device tables to `--context` instead of always allocating 262,144 positions. The generic binding validator uses the same extent. The full 262,144-position file is still hash-checked at load; table generation and every reachable value are unchanged.

This prevents the new 262K capability from increasing the two-card 64K footprint. A fixed-extent 262K binary had failed rank-1's 30 GiB arena admission before this change.

## Two-card 64K service

- Both F32 context oracles: zero differences.
- Batched prefill: 13/13 passed.
- Continuation and prior-build session compatibility passed.
- Cold 12-prompt suite: all **5,965 text hashes** matched the frozen suite, every request had `cached_tokens=0`; median **66.208671 tok/s**, in line with B24's 66.19.
- Self-test observations: 67.83 and 68.86 tok/s.

## Native 262K four-stage recheck

Cards 23/27/43/47 completed the same 32-token target-only run with identical outputs, `passed=true`, no live worker PIDs and exit code 0 from every stage. The full 262K RoPE tables are used on this path.

Files: `main.cpp` context-sized allocations, `kernels.hpp` context-sized binding validation, and service receipt `6280724f7c75.json`.
