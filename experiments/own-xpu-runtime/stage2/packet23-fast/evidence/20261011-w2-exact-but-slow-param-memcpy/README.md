# Packet 23 on the cards: fused schedule is bit-exact; a per-launch copy makes it 50 times slower (2026-10-11, 18:31–19:22 UTC)

All windows on this boot with a clean kernel log.

- K0 (kernel-compile smoke) passed in 6 s; every kernel fits the card's 2,048-byte
  argument limit.
- K1a and K1b (two fresh owners, card 3): fused GEMV bundles 553/553 and non-GEMV
  72 fixtures + 6 chains + 8 controls + adapter cases, fused == unfused == host bytes.
- W0 two-card canary passed.
- **W2, two cards, 64 tokens, fused schedule (876 launches per token): 64/64 tokens and
  384/384 layer fixtures equal to the v2 oracle.**
- **Speed: 4,445 ms per token (0.22 tok/s).** The scratch build of the unfused runtime
  does 83 ms.

Host profile during W2 ([perf-children.txt](perf-children.txt), [perf-self.txt](perf-self.txt)):
73% of the samples are under `ur_command_list_manager::appendUSMMemcpy` in the Level
Zero adapter, spinning in `sched_yield`. The kernel-argument repair moved each
kernel's parameters into a block that is copied to the card with `queue.memcpy`
before the launch. On this stack that copy call waits for the queue's earlier work by
yielding in a loop, and a `nice 19` process that yields loses the CPU for milliseconds
at a time whenever anything else wants it: about 5 ms per launch, 876 launches per
token. The CPU mock's submission micro-benchmark (0.29 µs) cannot see this.

Rule that follows: nothing may be copied to the card per launch. Parameter blocks are
written once when the plan is built; per-token values go through one small state
block per card.
