# Qwen3.8 Flash-Next HC-up grouped dynamic-M source result

Date: 2026-08-31

Status: default-off source candidate qualified; build and endpoint not authorized

The scheduler-bound M1--64 treatment is preserved in local vLLM commit
`797769b34` and tracked patch `0033` (SHA-256
`1944280fa2f3debf684d1ade665b8d40237edf866fc0415bb53f43b1f1ea71bb`).
It retains the original environment flag and all 97/TP4/PP1/MTP0/eager/
selective-PLE guards, adds the exact one-sequence/64-token scheduler contract,
and replaces mutable row state with an immutable 65-entry XPU table plus a
registered zero-copy identity alias that survives official layerwise reload.

The first focused test invocation is retained as an invalid-harness negative:
3 passed and 2 failed because the fake packed-matmul implementation was
incorrectly compared to contiguous authority beyond M1, and the real staged
extension had not been preloaded. It observed no source-runtime failure. The
fake oracle was relabeled and corrected to its actual packed-matmul operation;
the real-operation test was then run with the exact staged extension preloaded.

Corrected qualification passed:

- 5/5 focused tests, including native grouped exactness for every M1--64;
- true overlapping native M7/M37 calls on two XPU streams;
- immutable rows/weight/input and fresh distinct outputs;
- official reload preserving Parameter, packed buffer, rows table, and alias,
  followed by exact post-reload M37 inference;
- scheduler, input, state, and malformed-return fail-closed tests;
- 25/25 separate Qwen configuration tests.

Independent final source review found no blocker. This source and test result
does not authorize a treated runtime build or endpoint load. The next step is
a separately frozen build identity and target-only endpoint A/B packet; all
protected throughput and quality claims remain unchanged.
