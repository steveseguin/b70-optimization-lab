# MiniMax Async Scheduling Screen

Goal: test whether vLLM async scheduling is a quality-preserving speed lever for the current MiniMax M2.7 AutoRound TP4 stack.

The explicit async-on candidate used a fresh cache root and passed the promotion gate before benchmarking:

- Cache root: `/mnt/fast-ai/vllm-cache-exp/minimax-async-scheduling-on-20260521T160043Z`
- Raw145 n64 exact: passed
- Raw145 n256 exact: passed
- Semantic suite n64 r2: passed
- Arithmetic repeat n64 r8: passed

Warm p512/n1536 throughput after two discarded warmups and four measured repeats:

- Explicit async-on: `93.550880` output tok/s, `124.734506` total tok/s, stdev `0.016861`
- Paired default: `93.499726` output tok/s, `124.666301` total tok/s, stdev `0.011832`
- Accepted quality-clean LocalMaxxing reference: `93.443623` output tok/s, `124.591498` total tok/s

The vLLM logs show the current default path also enables asynchronous scheduling, so explicit async-on is not a meaningful new optimization. It is quality-clean, but the uplift is too small to submit as a new public result.

The explicit async-off speed screen compiled a separate graph and dropped to:

- Async-off: `86.112369` output tok/s, `114.816492` total tok/s

Conclusion: keep async scheduling enabled/default. Disabling it is a clear decode regression and is not worth quality promotion. The next useful work should stay focused on reducing the remaining all-reduce/graph boundary cost rather than toggling the scheduler.
