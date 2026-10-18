# Packet119: warm selected DOWN weights during gate/up

CPU preparation, October 18. No GPU, service, live queue, privileged command,
power setting, host-memory setting, or page-cache setting changed in this work.
`git pull --rebase` refused unrelated dirty orchestration files; after `git fetch`,
HEAD and origin/main both read `7d87c81c479cbccc1bc07945975cd27e8eb35e78`.
Those dirty files and every existing packet remain untouched.

The new [packet](../experiments/own-xpu-runtime/stage2/packet119-down-warm/README.md)
copies packet118's native source. The only runtime dimension added is
`down_warm=production|p119`; the control retains packet118's E1 half-cache,
DOWN tile16, other-fusion, target-head split, 80,128-row draft prefix and BF16
state. Packet110's old non-tile16 DOWN time is an opportunity clue, not this
experiment's control. No closed geometry, table, GRF or next-block-prefetch arm
is reopened.

Each IQ4 DOWN expert is 2560 × 360 = **921,600 bytes**. Ten selected experts
need **9,216,000 bytes**. Two tokens with disjoint routes need 18,432,000 bytes,
but the present M=2 engine executes each target row serially, so warming serves
one gate/up-to-down interval at a time. All 384 preregistered packet100b route
vectors have ten distinct expert IDs. In the complete capture, 6,048 adjacent
accepted token pairs at the same layer/rank/prompt have 10–20 distinct experts
(mean 16.5126). No prompt or route is selected by candidate speed.

The candidate reads one uint32 per 64-byte DOWN cache line, without changing any
model arithmetic. Gate/up's 5,120 work-items per expert divide the loads across
its final three decode steps. At most 14,400 lines are warmed per expert.
The actual bound is the smaller of the full selected footprint and 75% of the
runtime-reported global cache; missing cache metadata refuses the candidate.
Volatile reads preserve discarded loads without a branch that could write a
model output. ISA validation must also check the load's cache policy.

No retained B70 cache-capacity measurement was found. The queued micro reports
the runtime cache properties and probes 1, 2, 4, 8, 16, 24, 32, 48 and 64 MiB
with eight cold/warm pairs each. The reported property is not labeled a measured
L2 capacity; the timing curve remains diagnostic evidence.

The pair harness runs gate/up, unchanged activation, and tile16 DOWN on every
one of the 384 real captured routes. Both orders run in each of two fresh
processes, with a 512 MiB device read scrub before each arm and none between
operators. All gate/up, activation, DOWN, status and control bytes must match.
Each process and each order must have median matched-route
`(expsgate + expsdown)` ratio at most **0.85**. Activation-inclusive timing is
retained separately. Synthetic weights/activations make this an operator
diagnostic, never a model speed headline.

GNU and Intel each passed two fresh host-only byte checks. Every run covered
ten finite/exceptional/invalid-route cases, 50 output/status comparisons,
4,480 raw FP32 chain comparisons, unchanged DOWN bytes and seven cache-address
coverage cases. These checks establish source arithmetic parity per compiler;
device equality and equality to `iq3-p49-split32-v1` remain later gates.

The micro binary compiled and its two proposal entries passed temporary queue
planning. Each estimates 240 seconds and has a 1,200-second watchdog. The runner
refuses missing CPU/ISA prerequisites. The v5 one-load bracket is prepared in
parallel and may run only after both measured micro processes pass. It keeps
five switchable control/candidate views, checks inherited limits before native
exec, and includes the nonnegative drain timeout fix.

CPU commands use `nice -n 19 taskset -c 8-15,24-31 python3 -B`, stdin `/dev/null`,
CPU-entry-only 8 GiB address-space caps, and packet94's serial compile turn.
The task's storage bounds are 25 GB root free and 250 MB of new build files.
Build objects reused from the frozen parent are hash-bound, not rebuilt blindly.

## Micro milestone

The exact micro AOT image retains the extra DOWN load. Candidate and control
use 128 registers without scratch/spills and have the same two static store
sites. The new load uses default caching, with no uncached override. Its loaded
value has no arithmetic consumers. The retained LLVM/vISA/native excerpts bind
the DOWN allocation and expert/line address calculation to that load.
[ISA receipt](../experiments/own-xpu-runtime/stage2/packet119-down-warm/evidence/warm-isa.json).

Both strict micro proposals pass temporary queue planning after the CPU and
ISA prerequisites. Eleven analyzer refusal tests pass. The 1,200-second watchdog
is five times the estimated 240 seconds for each fresh process. The runtime
and coordinator still own the device equality and speed decisions.
