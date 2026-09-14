# Overnight worker reliability results

Readable tool output produced reviewed, tested patches for **all five original
issues**, up from three in the first trial. Both formerly failed issues passed
one additional attempt from new source snapshots. **Both new held-out issues
failed.** Keep the readable-output profile opt-in and experimental; retain the
original default. These small tasks do not establish dependable unattended coding.

This closes the [bounded registered campaign](overnight-2026-09-14-plan.md).
The eight-hour authorization was a maximum, not a reason to continue a profile
sweep after the registered work finished. No inference optimization or new model
speed/quality qualification is claimed. The existing two-B70 FP8 server was
reused throughout, without a restart or host-setting change.

## Corrected readable-output results

“Passed” requires the unchanged issue acceptance check on a stable final tree
and a separate agent's patch review. Human approval remains pending; every model
patch is unmerged. Repeats are confirmations, not additional unique issues.

| Issue | Role | Tests and review | Model requests | Elapsed seconds |
| --- | --- | --- | ---: | ---: |
| Keep hardware listings independent | target | Passed | 14 | 60.0 |
| Honor zero electricity costs | target | Passed | 23 | 111.1 |
| Reject invalid CLI numbers | control | Passed | 13 | 101.5 |
| Correct context-sweep batch latency | heldout | Unsolved | 40 | 187.0 |
| Reject an incomplete depth flag | heldout | Unsolved | 40 | 309.2 |
| Quoted download paths | control | Passed | 13 | 81.1 |
| Stop after the first failed request | control | Passed | 13 | 77.5 |
| Keep hardware listings independent | repeat | Passed | 14 | 60.1 |
| Honor zero electricity costs | repeat | Passed | 23 | 111.4 |

The five original issues plus two held-out issues therefore give **5/7 unique
issues passed**. Counting the two confirmations gives **7/9 attempts passed**;
those are different denominators. Both repeats used the same greedy seed and
continuously running server. They do not establish fresh-server qualification
or general exact-token determinism. Elapsed time includes source snapshots,
model calls, tools, acceptance and export.

The zero-cost patches meet the original behavior requirement and carry the
current browser engine cache stamp. Browser numeric inputs still declare
positive minima; typed or stored zero calculates correctly, but control validity
is a separate prospective v2 follow-up. The CLI patch passes the registered
malformed-number cases; practical upper bounds and safe-integer policy remain
integration questions. Full patch-specific findings are in the packet reviews.

## Candidates and failures retained

- **Thinking low:** all three automatic acceptance checks passed, but independent
  review approved only two patches. The zero-cost patch omitted the changed
  engine's browser cache stamp. That failed the registered review gate; it was
  not promoted. Sampling and output budget changed with thinking, so this was a
  client-profile comparison, not a reasoning-only causal test.
- **Initial readable-output screen:** all three attempts stopped after two
  malformed action replies, before any tool command or observation. A shared
  recovery change had retained the invalid assistant reply; the legacy greedy
  client omitted it from subsequent history while preserving raw evidence.
  The first hardware request, response and token IDs match the historical
  attempt. This does not establish runtime nondeterminism or an observation
  format effect.
- **Corrected readable output:** restored legacy nonthinking recovery, retained
  full thinking history in the thinking adapter, and performed the single
  registered corrected pass. Greedy generation, the original system and issue
  prompts, output limit and acceptance fixtures stayed fixed. Actual multiline
  tool output replaced JSON escaping. It cleared the three-task review gate,
  so the registered regression, held-out and repeat checks followed. No matched original-profile held-out runs
  were made, so their failures do not show that the original profile is better.
- **New batch-latency issue:** 40 calls surveying source, no edits or submission.
- **New incomplete-depth issue:** 40 calls, with an ineffective partial patch and
  alternating inverse edits. It never submitted acceptance. An independent
  check in a disposable copy still reproduces the original bug. Neither held-out
  failure was retried or rescued with solution hints.

The failed two-call thinking protocol probe is also preserved. Its second
request exposed a 446-versus-478 input-token mismatch: Chat Completions normalized
legacy `reasoning_content`, but `/tokenize` did not. The adapter now sends canonical
`reasoning` to both routes. A CPU-only tokenization check returned 478 for the
retained generation history. No extra protocol generation was used to overwrite
that failed receipt. Reasoning is retained separately and never parsed as a tool
command; truncated, cached or inconsistent replies stop before execution.

## Observed request timings

Each cell is the median over completed task requests, including completed
requests in failed tasks. Protocol probes are excluded. Context grows during
coding and differs between tasks and profiles: **these are session observations,
not matched speed comparisons or the fixed 512-token prefill benchmark.**

| Client profile | Calls | Input-token range | Prefill input tokens/s | Streamed output tokens/s | First token s | First answer token s | Valid action ready s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Thinking low: original three tasks | 63 | 486–20,771 | 3,355.8 | 53.5 | 2.91 | 4.54 | 5.18 |
| Readable output: all nine attempts | 193 | 451–23,054 | 3,380.0 | 56.8 | 2.49 | 2.49 | 4.97 |

Prefill divides actual input tokens by server prefill duration, from first
scheduled execution to first token. HTTP first-token wait includes scheduling
and transport; first-answer wait also includes preceding reasoning. Streamed
output rate uses received token intervals after the first token and includes
reasoning tokens in the thinking profile. A valid action becomes ready only
after the complete reply, evidence capture and format validation. Invalid
formats have no action-ready time: the readable profile has 184 valid-action
timings among 193 completed replies; all 63 thinking task replies were valid.
No prompt caching was allowed; full token
accounting is retained. See the separate [fixed-input FP8 prefill results](../qwen38-27b-b70/notes/2026-09-14-fp8-prefill-focus-results.md).

## Prospective worker safeguards

After freezing the model campaign, two focused CPU changes close observed gaps:

- A separate [zero-cost v2 task](../../worker/tasks/ml-zero-electricity-cost-v2.json)
  adds browser cache-stamp and numeric-control validity requirements to the
  unchanged v1 behavior gate. Its [CPU receipts](data/2026-09-14-worker-hardening/acceptance/README.md)
  show that baseline, stale stamp and positive input minima fail as intended.
  A manually constructed gate fixture passes; it is not a model-produced repair.
- An exact two-command cycle guard warns after the same commands, exit statuses
  and returned outputs repeat three times, then stops before another cycle begins
  if the next command repeats its first action. A different command or submission
  can continue. [CPU replay](data/2026-09-14-worker-hardening/cycle/README.md)
  catches the failed depth trace and checks the acceptance-passing traces.
  Matching output does not prove hidden filesystem state made no progress.

These safeguards were added after the measured runs. CPU checks and recorded
trace replay do not measure how the model responds to new feedback, prove an
acceptance gain, or establish time/token savings. No further model trial is
claimed for them.

## Evidence, setup and remaining work

- [Corrected campaign summary](data/2026-09-14-readable-observations/summary.json),
  [manifest](data/2026-09-14-readable-observations/manifest.json),
  [archive, patches and reviews](data/2026-09-14-readable-observations/README.md).
- [Initial screen, including failures](data/2026-09-14-profile-screen/README.md).
- [Original five-issue history](README.md#first-five-issue-trial), unchanged.
- [Worker installation, API and profile commands](../../worker/README.md).
- [Public overview](https://neural.download/worker/).

The model remains official Qwen3.8 27B FP8 revision
`017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`, TP2/MTP1, prefix caching off,
33,024 total tokens, scheduling budget 4,096 and one active sequence. Runtime,
image digest, launch settings and exact harness sources are archived. The
[qualified FP8 package](../../packages/qwen38-27b-fp8-tp2-b70/README.md) is unchanged.
Client profile changes do not alter its historical benchmark claims.

All task CPU containers stopped before final patch export. Original repositories
were never mounted into them. Server logs are timestamped live captures, not a
stopped-server postflight. The healthy localhost API is left available. No cloud
fallback, external message, new model, competing GPU task, server restart or
power/memory-setting change was used.

The useful next step is a reviewed integration of selected patches and, only
when more reliability work is wanted, a small preregistered set of new tasks.
Fresh-host setup, network-dependent builds, larger projects, concurrent users
and broad autonomous reliability remain unqualified.

## Publication checks

Local validation passed 103 worker CPU tests and 91 guide/renderer tests. All
three frozen task packets verify, and the cycle replay checks 13 automatically
acceptance-passing traces plus the failed depth trace. The package catalog and
model pages regenerate without model-result changes. Repository document links
and 5,531 paths across 50 manifests pass. Desktop and mobile pages were checked
with and without JavaScript, with no page overflow.

The separate repository-wide literal-pin scan is not clean: 86 of 317 pins
match and 231 have the known historical drift against two unrelated frozen
Flash-Next verifier files; no target is absent. These pins were not rewritten
by this work. Worker CI now verifies the original trial, both new campaign
packets and the prospective cycle replay on subsequent relevant changes.
