# 4B worker trial: no completed patches

The pinned Qwen3.5 4B W4A16 model completed neither frozen coding task.
Both attempts exhausted their 20-step allowance without changing a workspace
file or attempting final acceptance. Independent reviews rejected both.

| Task | Requests | Elapsed | Result |
|---|---:|---:|---|
| Catalog pending headlines | 20 | 91.05 s | Diagnosed unsafe metric access, then searched for tests in the wrong directory; no edit |
| Context number boundaries | 20 | 198.56 s | Reproduced the bug; final temporary script did not apply a fix; no edit |

The exact acceptance paths were present in the first model request. The model
mostly searched under `/workspace` instead. Commands varied enough that the
existing exact repetition guards did not fire. These are task failures, not
server, response-format or hardware failures. More context or faster decoding
alone would not demonstrate that this behavior is fixed.

The representative transport canary passed. All 40 task requests completed;
the original repository and each baseline remained unchanged. Both full
source snapshots were checked after their CPU containers stopped. Complete
compact evidence, including source hash inventories, requests, empty patches,
review bindings and frozen-tree checks, is preserved in
[catalog-packet](results/catalog-packet/) and
[context-packet](results/context-packet/). Both archives passed independent
read-back verification and were fsynced before their owned RAM snapshots were
removed. No patch was merged.

## Recall was refused before generation

The complete five-document prompt tokenized to **14,008 input tokens**, exceeding
the preregistered 12,000-token allowance. Reserving 4,096 answer tokens would also
exceed the server's 16,384-token context. The harness refused without truncating
the sources or generating an answer. This is a context-admission result, not a
recall-quality score. Preserve the [prompt and refusal](results/memory/).
A future larger-context trial should budget at least 18,104 total tokens for
this exact prompt and output allowance, and recount with its own tokenizer.

## State left behind

The single 4B server stopped gracefully, exited zero, left the render nodes
idle, and passed all four postflight card checks. There was no new kernel
fault, OOM, restart, driver reset or host-setting change. See
[shutdown](results/server/shutdown.json) and
[postflight](results/server/postflight-health.json).

All twelve pinned model files remain in the fully hash-verified cold copy at
`/mnt/usb-models/worker-models/qwen35-4b-w4a16-20261007/7a613872f394578b0b52b683ff4ac47516b4bcaf/`.
The external drive is unmounted. Only the temporary RAM copy was released
after successful shutdown and verified preservation. The earlier 0.8B model
caches, research artifacts, LTX and Flash-Next remain preserved.

## Decision

Do not promote this 4B setup as a coding worker or tune it against these two
observed tasks. The intended 27B trial is still separate and unrun. First close
its concrete model-intake and runtime gaps, with no speculative-kernel safety
claim borrowed from these tests and no use of the protected two-card endpoint.

One focused future harness change is justified: explicitly explain that the
acceptance command points to a separate read-only `/acceptance` mount, and ask
the worker to use that exact path rather than search the source tree for it.
Keep this as a proposed change until tested on fresh tasks; the current worker
instructions remain unchanged. Do not expand into a general prompt-tuning
campaign or attach lab memory to an unqualified worker.
