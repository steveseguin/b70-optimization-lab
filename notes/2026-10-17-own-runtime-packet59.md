# Packet 59: faster proposals, same target verifier

The [separate packet](../experiments/own-xpu-runtime/stage2/packet59-fast-draft/README.md)
is based on packet56. It leaves that packet and the concurrent screen work
alone. Preparation is CPU-only, nice 19 on cores 4–15,20–31, one compiler at a
time. There are no GPU launches, service changes, weight payload reads, sudo,
host-setting changes or stops of another job.

The target's source, arithmetic, dispatch, controller and oracle are unchanged.
The draft still proposes from head rows [0,91,392). Its BF16 and INT8 formats
need their own readers, so the new kernels port the useful target schedules
without misreading those weights. Split32 attention and the selected fast
router are reused directly. Vector loads, virtual lanes and split reductions
speed candidates for the other projections. Ten standalone operations are
fused into their producers; draft norms take one launch each. The head and
argmax retain their fastest compatible implementations.

The [full per-kernel table](../experiments/own-xpu-runtime/stage2/packet59-fast-draft/README.md#draft-changes)
and [budget](../experiments/own-xpu-runtime/stage2/packet59-fast-draft/budget.json)
record every change and its uncertainty. Packet52's losing free-order grid is
not repeated. Its small winners used other formats and older controls; there
is no evidence they beat the selected later schedules for this draft.

The estimate is about 0.38–0.40 ms less draft time: analysis 0.381 ms, code
0.395, documentation 0.382, operations 0.387, prose 0.385 and structured writing
0.379. If acceptance stays unchanged, that is roughly 1.5% total speedup.
These are explicit planning assumptions, not packet59 measurements. Some fast
target schedules may not transfer to BF16/INT8. Acceptance must be measured.

The lean CPU gate passed in 6.06 seconds: 132 retained parent source files are
identical, 96 small target layer fixtures and 24 output tokens equal packet56,
and two fresh candidate processes agree on 27 draft proposals. Two fresh
production-width synthetic runs agree on 104,032 output bytes. No large model
or full head fixture was loaded. The [read-only review](../experiments/own-xpu-runtime/stage2/packet59-fast-draft/REVIEW.md)
found no correctness blocker; its misleading kernel-name receipt finding was
fixed before these gates.

The device build and final CPU seal are the remaining preparation steps at
this implementation commit. The [coordinator command](../experiments/own-xpu-runtime/stage2/packet59-fast-draft/WINDOW.md)
uses the new screen tool, with no edits to that tool. Only twelve exact prompts
and a class-balanced rate above 46.962697 justify a full packet56-style chain.
A screen cannot be submitted, and a screen-only seal does not qualify the full
chain. The coordinator retains device ownership and must let packet58 finish
and release its pinned host memory before admitting TP2 work.
