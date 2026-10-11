# Packet18 do not repeat

| Mistake / closed preparation lever | Evidence / decision | Revisit condition |
| --- | --- | --- |
| SYCL object outliving the owner's context release | W0 passed its device work then aborted at bundle/context destruction. Inner canary scope now destroys borrowers before shutdown; two-card decode lifetime audit and mock gates in [LIFETIME.md](LIFETIME.md). | Never retain a bundle, kernel, event, queue or capturing lambda past native release. Fresh W1/W0 and two-card exit gates are still required. |
| a watchdog set to the expected run time | Incident 5 (2026-10-11 02:34 UTC): a stop during startup/JIT can fault the engine. The 30/50 s watchdogs are withdrawn; expectations only report. [Deadline audit](DEADLINES.md). | Never restore a short total-time cutoff; keep first-use JIT and at least 4× margin in every signal deadline. |
| events chained across two cards' queues | Packet16 incident and packet19 audit; packet18 now fences, retires and rejects foreign events. [Independent review](review-queue-isolation.md). | Separate tiny preregistered device experiment after recovery; never a fallback. |
| environment keys added to a prepared window | Faulting packet16 used NEOReadDebugKeys/EnableDeferBacking; no passing own-runtime device run did. Every packet18 window refuses these and unknown keys before latch creation. | Separately preregistered experiment, outside this packet. |
| Never-written full snapshot readback | Packet19 sanitizer; initialize every byte before first capture, including unowned slices. | Never restore uninitialized readbacks. |
| Precision flags only on compilation | Packet17 one-input log mismatch; packet18 asserts generated compile and link flags. | Never omit link precision flags. |
| Platform exp/log/trig in v2 device path | Recursive include grep at configure/build. | A separately named arithmetic identity and new exactness evidence. |
| Comparing W1 against v1 device output | W1 binds v2 CPU 384 fixtures and 8 tokens directly. | Never substitute token agreement for layer equality. |
| Copying control flags twice per non-GEMV site | Direct bindings remove 1,190 launches/token; CPU gates and independent lifetime review. | A changed owner/control ABI. |
| Combining all dense shapes under split4 | Frozen and R5 shape-specific trees preserved. | Separately named arithmetic identity. |
| Re-expanding R5 dense weights at every CPU token on a large-memory host | Interrupted CPU receipt retained; resident CPU gate passes 384 fixtures and eight tokens. | Use streaming only when RAM admission requires it. |
| Treating build/CPU parity/calculated bytes as device qualification | No device ran; W0/W1/W2/W3 and repeats pending. | Separately admitted completed windows. |
| Editing active packet16 or packet17 source | Packet18 owns all local adaptations; provenance hashes retained. | Never during these hash-bound windows. |

[Closeout](CLOSEOUT.md).
