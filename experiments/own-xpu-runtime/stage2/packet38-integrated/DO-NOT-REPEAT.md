# Packet38 do not repeat

| Closed error | Required behavior |
| --- | --- |
| Release draft scratch on shared target owner | Keep allocations alive through request reset; zero in place. |
| Reuse request state | Reset every target/draft mutable allocation, both banks and host controls. |
| Count reset uploads in the next request | Reset timing counters after all maintenance work. |
| Select QSA using capacity128 fixture | Time capacity256 at 88/104/120/136/152/256; retain 88..152 and 256 for exactness. |
| Require class tables in token mode | Mode-specific receipt fields only. |
| Treat old journal text as new fault | Use this wrapper's own cursor. |
| Latch admission refusal | No child launch means no fault latch. |
| Treat cache files as proof of driver cache hits | Report files present and first-position time; hit is unobservable. |
| Retry a failed rank/window | Write receipts, request one bounded stop, preserve ownership. |
| Credit CPU controller timing as model speed | CPU handover microbenchmark only. |
| Report TSan runtime abort as pass | Retain GCC13 startup failure; use the completed LLVM22 CPU TSan gate. |
| Leave inactive QSA score scratch unchanged | Preserve incumbent negative-infinity tails and compare the full score buffer. |
| Omit draft functor members from argument audit | Serialize dense A pointer, merge width and small-family metadata. |
| Run queued native work after abort | Check cancellation even when a sequence is already ready. |
| Compare only per-cycle rank0 dumps | Record final states from both ranks for controller equivalence. |
| Let failed evidence writes skip teardown | Attempt receipts first, then always request bounded cooperative stop; `review-resume-storage-gates.json`. |
| Scan mutable scratch with an unprotected stat | Ignore only vanished-file races; propagate other errors; `storage-race-gates.json` and `native-mini-resume-storage-race-failed.json`. |
| Keep oversized fixture outputs after hashing | Archive text and original hashes, then discard each completed scratch tree; `validation-gates.json`. |
| Delete compressed state inventories while preserving only their hashes | Retain their exact compressed bytes and verify them before cleanup; `suite-export-retention-gates.json`. |
| Warm the first measured suite prompt | Use a distinct synthetic five-token request, then fully reset; `suite-warmup-gates.json`. |
| Let warm-up EOS skip a required head | Suppress EOS termination only for excluded warm-up and require two outputs; measured requests keep normal EOS handling. |
| Compare parent files while calling them pinned commits | Read immutable Git objects; label newer working-tree hashes separately; `source-overlay.json`. |
| Seal a stale no-launch admission pass | Recheck its source hashes and exact consumed seal contract; `test_window_seal_admission.py`. |
| Require the suite candidate hash in inherited real-mode receipts | Bind the inherited packet33 dispatch and the packet38 suite candidate separately; qualify the latter through its own kernel gates and actual suite. `suite-preflight-refusal.json` preserves the no-launch refusal. |

| Time the full exactness grid without multiplying measured wall cost | K2's old 66 × 216 s exceeded its watchdog. Use six timing lengths, retain all K1 lengths, and refuse expected+17 s above watchdog/4. See [repair](evidence/20261012-k2-repair/README.md). |
| Allocate 400 QSA states per comparison and call it the in-model baseline | Use resident QSA buffers and reusable readback; verify every repetition. Old ~1 ms rows do not establish resident incumbent cost. Allocation-ledger scans and 30,400 blocking uploads per shape made setup dominate. |

Prior packet36 and37 negative histories remain in their read-only directories.
