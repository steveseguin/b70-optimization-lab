# Project decision answers

These answers describe the five frozen project records at repository cutoff `a96a072efa4a6611d79ef323bef507da42607885`. Historical results retain their original dates and configurations; this is not a live host-status report. The records are agent-curated and attribute some instructions to an owner without authenticating the original human messages.

The text below preserves the first search submission, which passed independent review of all 38 essential criteria. [Raw answers](results/search/answers.json) and [criterion review](results/search/semantic-review.json) retain exact quotations, explanations and provenance.

## Resident service policy

The September 13 preference for one continuously running server and endpoint reuse was withdrawn as an agent’s reading. The October 3 replacement permits a server only for an experiment: start it, measure, stop it gracefully, and leave the cards empty. A resident server may be started, restored, queued, or auto-launched only if the owner asks for one; a campaign must not automatically put the service back.

[AGENTS.md, lines 25–31](https://github.com/steveseguin/b70-optimization-lab/blob/a96a072efa4a6611d79ef323bef507da42607885/AGENTS.md#L25-L31).

## Approval authority

The rules attributed to the owner override everything else in the policy file, older notes, and recipes. A reboot always requires the owner’s explicit authorization. These are role-based attributions in the supplied policy, not authenticated authorship by a named human.

[AGENTS.md, lines 17–18](https://github.com/steveseguin/b70-optimization-lab/blob/a96a072efa4a6611d79ef323bef507da42607885/AGENTS.md#L17-L18); [AGENTS.md, lines 59–62](https://github.com/steveseguin/b70-optimization-lab/blob/a96a072efa4a6611d79ef323bef507da42607885/AGENTS.md#L59-L62).

## KV cache precision

The default is a full 16-bit KV cache: BF16, or FP16 where the runtime uses it. FP8 or other compressed KV may be used only when a 16-bit cache is unavailable for that model or the owner explicitly authorizes it. Neither exception makes compressed KV a default or headline configuration.

[AGENTS.md, lines 46–52](https://github.com/steveseguin/b70-optimization-lab/blob/a96a072efa4a6611d79ef323bef507da42607885/AGENTS.md#L46-L52).

## Live state authority

CURRENT.md is the sole cross-repository authority for live card contents, the active optimization lane, protected work, and immediate next actions. Old experiment notes alone cannot establish what is running now. Before operational changes, verify Git status, relevant processes, and the actual endpoint, and preserve paths marked active or protected in CURRENT.md.

[AGENTS.md, lines 170–179](https://github.com/steveseguin/b70-optimization-lab/blob/a96a072efa4a6611d79ef323bef507da42607885/AGENTS.md#L170-L179).

## Million token campaign snapshot

At the October 7 follow-up, the million-token attempt had progressed from incomplete to completed: quoted mode scored 24/24, nonvoid, in 47.9 minutes. The new snapshot retained all prior attempt IDs and contained 31 attempts: 29 completed, one interrupted, and one incomplete. The 480K quoted seed-1 attempt remained incomplete, and its task asks 21 questions, not 24. The earlier snapshot remains unchanged as the record of what was known then.

[2026-10-07-context-campaign-followup.md, lines 3–8](https://github.com/steveseguin/b70-optimization-lab/blob/a96a072efa4a6611d79ef323bef507da42607885/experiments/qwen38-27b-b70/notes/2026-10-07-context-campaign-followup.md#L3-L8); [2026-10-07-context-campaign-followup.md, lines 10–15](https://github.com/steveseguin/b70-optimization-lab/blob/a96a072efa4a6611d79ef323bef507da42607885/experiments/qwen38-27b-b70/notes/2026-10-07-context-campaign-followup.md#L10-L15).

## Missing retention task

No. ret120q2, the quoted retention seed-1 block, failed during planning because its task file was missing. It had no model score. The existing 35/36 belonged to seed 0. The wrapper continued to the next block, so its final plan-complete message did not establish that every cell completed.

[2026-10-07-context-campaign-followup.md, lines 19–24](https://github.com/steveseguin/b70-optimization-lab/blob/a96a072efa4a6611d79ef323bef507da42607885/experiments/qwen38-27b-b70/notes/2026-10-07-context-campaign-followup.md#L19-L24).

## Durable r4 failure decision

The second summary trial exhausted its fixed 8192-token output cap entirely on reasoning and returned no answer, with finish_reason=length. This was a measured bounded-model failure, not a transport or GPU failure. The harness recorded the failure and stopped the server without continuation or retry. r4 must remain frozen and failed, with no raised cap or relabeling of the incomplete matrix. Held-out admission stayed closed and no held-out seeds were used.

[2026-10-07-durable-context-r4-result.md, lines 8–12](https://github.com/steveseguin/b70-optimization-lab/blob/a96a072efa4a6611d79ef323bef507da42607885/experiments/qwen38-27b-b70/notes/2026-10-07-durable-context-r4-result.md#L8-L12); [2026-10-07-durable-context-r4-result.md, lines 26–31](https://github.com/steveseguin/b70-optimization-lab/blob/a96a072efa4a6611d79ef323bef507da42607885/experiments/qwen38-27b-b70/notes/2026-10-07-durable-context-r4-result.md#L26-L31); [2026-10-07-durable-context-r4-result.md, lines 35–39](https://github.com/steveseguin/b70-optimization-lab/blob/a96a072efa4a6611d79ef323bef507da42607885/experiments/qwen38-27b-b70/notes/2026-10-07-durable-context-r4-result.md#L35-L39).

## Limits of the speed comparison

The notes support neither a general speed verdict nor a contradiction. The legacy million-token pair had matching input-stream and expected-answer hashes: quoted scored 24/24 in 47.9 minutes versus read mode’s 23/24 in 62.2 minutes, an observed 23.0% elapsed reduction for that one pair. It was not repeat-confirmed and did not establish correctness of every intermediate state. In r4, a fresh server had prefix caching explicitly disabled and completed primary trials were verified uncached; quoted was slower than archive in both completed pairs, but the incomplete matrix yielded no qualifying speed signal or verdict. These are different task/protocol scopes, not interchangeable matched replications.

[2026-10-07-context-campaign-followup.md, lines 3–8](https://github.com/steveseguin/b70-optimization-lab/blob/a96a072efa4a6611d79ef323bef507da42607885/experiments/qwen38-27b-b70/notes/2026-10-07-context-campaign-followup.md#L3-L8); [2026-10-07-durable-context-r4-result.md, lines 3–6](https://github.com/steveseguin/b70-optimization-lab/blob/a96a072efa4a6611d79ef323bef507da42607885/experiments/qwen38-27b-b70/notes/2026-10-07-durable-context-r4-result.md#L3-L6); [2026-10-07-durable-context-r4-result.md, lines 19–24](https://github.com/steveseguin/b70-optimization-lab/blob/a96a072efa4a6611d79ef323bef507da42607885/experiments/qwen38-27b-b70/notes/2026-10-07-durable-context-r4-result.md#L19-L24); [2026-10-07-durable-context-r4-result.md, lines 51–54](https://github.com/steveseguin/b70-optimization-lab/blob/a96a072efa4a6611d79ef323bef507da42607885/experiments/qwen38-27b-b70/notes/2026-10-07-durable-context-r4-result.md#L51-L54); [2026-10-07-durable-context-r4-result.md, lines 63–64](https://github.com/steveseguin/b70-optimization-lab/blob/a96a072efa4a6611d79ef323bef507da42607885/experiments/qwen38-27b-b70/notes/2026-10-07-durable-context-r4-result.md#L63-L64); [AGENTS.md, lines 420–423](https://github.com/steveseguin/b70-optimization-lab/blob/a96a072efa4a6611d79ef323bef507da42607885/AGENTS.md#L420-L423).

## R189 publication scope

R189 was published as the R187 line’s 2K–32K real-content context-depth profile, in package performance profiles and the guide table. It used the R156 image via R187 wrappers, whole-graph COMPILATION_CONFIG splitting_ops=[], capacity 33,024 tokens, one slot, and 4,096-token chunked prefill. The R150 protocol had three real-content classes, three requests per depth, 128 output tokens, cache zero, and canaries. MTP1 equaled MTP0 at the six measured active-context depths: 2048, 4096, 8192, 16384, 24576, and 32768. It does not establish every speculative MTP depth or concurrency level.

[2026-09-03-qwen38-fp8-r187-real-content-depth-r189-result.md, lines 3–5](https://github.com/steveseguin/b70-optimization-lab/blob/a96a072efa4a6611d79ef323bef507da42607885/experiments/qwen38-27b-b70/notes/2026-09-03-qwen38-fp8-r187-real-content-depth-r189-result.md#L3-L5); [2026-09-03-qwen38-fp8-r187-real-content-depth-r189-result.md, lines 9–16](https://github.com/steveseguin/b70-optimization-lab/blob/a96a072efa4a6611d79ef323bef507da42607885/experiments/qwen38-27b-b70/notes/2026-09-03-qwen38-fp8-r187-real-content-depth-r189-result.md#L9-L16); [2026-09-03-qwen38-fp8-r187-real-content-depth-r189-result.md, lines 18–20](https://github.com/steveseguin/b70-optimization-lab/blob/a96a072efa4a6611d79ef323bef507da42607885/experiments/qwen38-27b-b70/notes/2026-09-03-qwen38-fp8-r187-real-content-depth-r189-result.md#L18-L20).

## R197 qualification scope

As of R197, MTP depth 4 on the R187 line, using R156 with splitting_ops=[] and num_speculative_tokens=4, was described as the fastest lossless single-user profile so far. The paired rates were 82.447 and 82.345 tok/s, centered at 82.396, about 4% above depth 3’s 79.183. It passed the recorded single-user oracle and repeat checks. High concurrency was not fully qualified: the first ladder was exact only through c16, scored 30/32 at c32 and 58/64 at c64, and the second ladder R201 was still queued.

[2026-09-04-qwen38-fp8-mtp4-whole-graph-r197-result.md, lines 3–3](https://github.com/steveseguin/b70-optimization-lab/blob/a96a072efa4a6611d79ef323bef507da42607885/experiments/qwen38-27b-b70/notes/2026-09-04-qwen38-fp8-mtp4-whole-graph-r197-result.md#L3-L3); [2026-09-04-qwen38-fp8-mtp4-whole-graph-r197-result.md, lines 9–13](https://github.com/steveseguin/b70-optimization-lab/blob/a96a072efa4a6611d79ef323bef507da42607885/experiments/qwen38-27b-b70/notes/2026-09-04-qwen38-fp8-mtp4-whole-graph-r197-result.md#L9-L13); [2026-09-04-qwen38-fp8-mtp4-whole-graph-r197-result.md, lines 16–18](https://github.com/steveseguin/b70-optimization-lab/blob/a96a072efa4a6611d79ef323bef507da42607885/experiments/qwen38-27b-b70/notes/2026-09-04-qwen38-fp8-mtp4-whole-graph-r197-result.md#L16-L18); [AGENTS.md, lines 514–514](https://github.com/steveseguin/b70-optimization-lab/blob/a96a072efa4a6611d79ef323bef507da42607885/AGENTS.md#L514-L514).

## Identity of the original human author

**Not established by this corpus.** These five supplied files attribute the standing rules to the owner and the withdrawn September 13 wording to an agent’s reading; they do not establish a named human as the author of the withdrawal. Hostnames and /home/steve paths do not authenticate authorship. This is a limit of the supplied corpus, not a claim that the human’s identity is unknowable elsewhere.

[AGENTS.md, lines 17–18](https://github.com/steveseguin/b70-optimization-lab/blob/a96a072efa4a6611d79ef323bef507da42607885/AGENTS.md#L17-L18); [AGENTS.md, lines 25–31](https://github.com/steveseguin/b70-optimization-lab/blob/a96a072efa4a6611d79ef323bef507da42607885/AGENTS.md#L25-L31).

## Unmeasured r4 duration

**Not established by this corpus.** No measured total elapsed time is supplied for durable r4’s seed-29 dispatch quoted trial. The result note says all six seed-29 trials did not start; times for the legacy million-token trial or the GPU-release clock time cannot serve as measurements for this unstarted trial.

[2026-10-07-durable-context-r4-result.md, lines 8–12](https://github.com/steveseguin/b70-optimization-lab/blob/a96a072efa4a6611d79ef323bef507da42607885/experiments/qwen38-27b-b70/notes/2026-10-07-durable-context-r4-result.md#L8-L12); [2026-10-07-durable-context-r4-result.md, lines 19–24](https://github.com/steveseguin/b70-optimization-lab/blob/a96a072efa4a6611d79ef323bef507da42607885/experiments/qwen38-27b-b70/notes/2026-10-07-durable-context-r4-result.md#L19-L24).
