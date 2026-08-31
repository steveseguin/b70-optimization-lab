# Qwen3.8 Flash-Next TP4 clone-elision analysis

Date: 2026-08-31
Status: closed as low priority without execution

The accepted XPU communicator implements an out-of-place reduction as
`clone()` followed by ordinary in-place `dist.all_reduce`. A clone-only
candidate initially looked like a safer remainder after the event-chain
candidate failed, but A28 bounds its value too tightly to justify the aliasing
risk or another endpoint load.

The A28 traces contain 99 instances per retained target cycle of the same BF16
copy kernel. That family includes all 97 `[1,2560]` communicator clones plus two
other copies. Its entire rank-mean duration is only `0.178914-0.185792 ms` per
cycle. Treating the whole 99-call family as removable is deliberately generous:
it would move the protected `5.515783 tok/s` result only to approximately
`5.521441 tok/s`, about `+0.103%`.

The raw host spans for the 97 `aten::clone` calls total roughly `6.45-6.65 ms`,
but A28's profiled host contexts inflated from the ordinary ~181 ms/token to
570-595 ms. That host sum is not a transferable endpoint saving. Even the
implausible assumption that all of it disappears would be only a loose ceiling,
not an expected result.

The source cost is also larger than it appears. XPU uses the registered
functional `torch.ops.vllm.all_reduce`, whose fake implementation promises a
fresh tensor. Mutating and returning its input from `XpuCommunicator` would
violate the alias contract. Source lifetime review confirms that A28's 48
attention projection outputs, 48 final local MoE outputs, and one synchronous-
PLE embedding output are disposable after their reduction. Even so, a correct
implementation still needs a distinct mutating operation plus Qwen-specific
call routing.

Do not spend another model load or current GPU-recovery cycle on clone-only
work. Preserve it as a low-priority component idea. The next safer lever is a
fresh-process CPU/L3 affinity screen against the ordinary accepted XCCL path,
because A28 directly measured ranks 2 and 3 as the last submitters in 270 of
291 collective observations.

Structured analysis:
[`20260831-tp4-count2560-clone-elision-analysis.json`](../data/20260831-tp4-count2560-clone-elision-analysis.json).
