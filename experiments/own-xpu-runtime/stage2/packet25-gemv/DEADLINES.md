# Duration estimates and hard limits

The [bound trace](timing-plan.json) gives about 178 us per paired expert gate/up,
130 us per down group, 101/62/118 us for qkv/z/qgate and 2,137 us for logits.
Those old spans set budgets; new reported execution times use GPU timestamps.

Every kernel submission in exactness, timing and both sequence modes is checked
against **2 ms** for non-logits and **10 ms** for logits, including each scratch
stage. These are at least four times the supplied measured spans (logits 4.68×,
others at least 11× in the selected classes), and all are strictly below 2 s.
Zero/reversed timestamps also fail. The kernel budget is checked after the one
sequence wait; the independent watcher handles a stalled queue.

Expected work is advisory only: K0 30 s plus 17 s first JIT; G1 200 s for two
owners including preparation and the 200-repeat operator/class/full-sequence
work, plus 17 s first JIT per owner. This is a planning allowance based on
roughly 27 ms of selected GEMV work/token and candidate/repetition counts,
not a new measurement. Candidate regressions and JIT variation can change it.

The minimum watchdog is `max(300, ceil(4*(work + owners*17)))`: K0 300 s;
G1 936 s. WINDOW.md uses 1,200 s for G1. Reaching an expected duration never
sends a signal. The hard watcher deadline/fault sends one SIGTERM after saving
failure; it allows 60 s for a cooperative drain and retains a stuck owner.
No timeout invokes a group kill. Every owner has a five-second kernel postflight.
