# Local coding worker: first five issues

The first milestone tests whether the preferred Qwen3.8 27B FP8 setup can turn
real repository bugs into tested patches. This is an experimental integration
trial, with independent acceptance checks and agent review. Human approval and
merging remain separate. No model performance optimization is claimed.

Use the [worker guide](../../worker/README.md) to install and run it, or read the
[original plan](../../worker/PLAN.md). The public overview is
[neural.download/worker](https://neural.download/worker/).

## Outcomes

**Three of five issues passed the independent acceptance checks; two remain
unsolved.** Seven attempts are retained: five selected runs, the invalid first
downloader attempt, and the first hardware-listing model failure.

| Issue | Independent checks | Requests | Elapsed |
| --- | --- | ---: | ---: |
| [Quoted download paths](data/2026-09-14-five-issues/patches/lab-download-manifest-paths.patch) | Tests passed | 21 | 2m 19s |
| [Stop after a failed request](data/2026-09-14-five-issues/patches/lab-smoke-first-request-failure.patch) | Tests passed | 12 | 1m 13s |
| [Keep hardware listings independent](data/2026-09-14-five-issues/reviews/ml-hardware-listing-isolation.md) | Unsolved | 21 | 1m 05s |
| [Honor zero electricity costs](data/2026-09-14-five-issues/patches/ml-zero-electricity-cost.patch) | Unsolved | 40 | 4m 49s |
| [Reject invalid CLI numbers](data/2026-09-14-five-issues/patches/ml-predict-cli-numeric-errors.patch) | Tests passed | 13 | 1m 24s |

### Observed request speeds

These medians cover completed requests in each selected attempt, including
requests from unsolved tasks. Input lengths vary; no controlled comparison.

| Issue | Input-token range | Median prefill (input tokens/s) | Median streamed decode (output tokens/s) |
| --- | ---: | ---: | ---: |
| Quoted download paths | 451–13,577 | 3,362.4 | 56.1 |
| Stop after a failed request | 460–8,230 | 3,421.8 | 57.8 |
| Keep hardware listings independent | 462–13,238 | 3,342.8 | 55.1 |
| Honor zero electricity costs | 484–26,860 | 3,162.9 | 55.1 |
| Reject invalid CLI numbers | 477–9,802 | 3,379.2 | 55.7 |

Elapsed time includes source snapshot creation, model requests, commands,
acceptance checks and patch export. These are small, deliberately scoped bugs,
not an estimate of success on arbitrary software projects. No generated patch
was applied to either original checkout.

## What ran

- Official Qwen3.8 27B FP8 revision
  `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`, two B70s, TP2/MTP1,
  33,024-token capacity, batch 4,096, one sequence, prefix caching disabled.
- The unchanged [qualified FP8 package](../../packages/qwen38-27b-fp8-tp2-b70/README.md),
  image `ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:7cd7bb16b1fd2e679f0230a38b2f0242fe1c278853867e697c0ce139be2133d2`.
  One server startup; the healthy server remains available for subsequent jobs.
- [mini-SWE-agent 2.4.6](https://github.com/SWE-agent/mini-swe-agent), with this
  repository's loopback-only model adapter and CPU sandbox. Dependencies are
  [hash-locked](../../worker/requirements.lock). No cloud model or fallback.
- Greedy sampling, seed 42, reasoning disabled, up to 2,048 output tokens per
  step, 28,000 input tokens, 40 steps, 20 minutes, three completion checks.
  Every generation retains full request/response evidence and cache accounting.
- The public Node 22 Bookworm CPU image is pinned in
  [config.json](../../worker/config.json). Commands use Python 3.11.2 and
  Node 22.23.2. CPU tasks have no network, GPU, original checkout, Docker socket,
  or host credential mounts. Only the source copy and temporary storage are writable.
- The [task definitions](../../worker/tasks/) name the source commits and
  issue-specific failure signatures. Lab source:
  `f7ad72e556f5508519fc1e806a1039b4a818511f`; ML Bottleneck source:
  [`8df1372c4f20fc8ae0bf4e35e1b75084327b17fc`](https://github.com/steveseguin/ml-bottleneck/tree/8df1372c4f20fc8ae0bf4e35e1b75084327b17fc).
  Source copies use `git archive`, without branches, worktrees or `.git` metadata.

## Failures retained and setup changes

The first downloader attempt was **infrastructure-invalid**. Docker's implicit
`noexec` temporary mount prevented mock commands from executing; the original
acceptance check timed out before reaching the intended bug. That attempt was
interrupted and its incomplete patch preserved. The corrected sandbox explicitly
allows temporary test executables while retaining the other container limits.
The runner now requires each bundled baseline's expected failure signature;
an unrelated environment failure stops before any model generation.

The first hardware-listing attempt was a **model failure**. It exhausted the
40-step limit while repeatedly reading the same function and returned an empty
patch. The runner now gives feedback on a third identical consecutive command
and stops on a fourth. A second attempt still repeated the command after feedback
and stopped after 21 requests, with no fix. This issue remains unsolved. Both
attempts remain in the packet; neither counts as a successful repair.

The zero-cost attempt also remains **unsolved**. Its patch introduced a casing
mismatch in an electricity-price variable, breaking SDK generation. It did not
correct that error before the repeated-command guard stopped it at request 40.
The partial patch and failing output are retained and rejected by review.

The initial downloader also spent many steps surveying repository conventions.
The system prompt now directs investigation toward the named implementation and
one nearby test. No solution code was inserted into the task prompts. These are
worker improvements, not changes to model weights, arithmetic or runtime.

The FP8 service was never restarted between tasks. Its existing helper monitors
GPU fault signatures throughout serving. All task CPU containers stop before
patch export; the final file tree must match the stable tree that passed acceptance.

## Evidence and interpretation

The compact [evidence manifest](data/2026-09-14-five-issues/manifest.json),
[summary](data/2026-09-14-five-issues/summary.json), and
[archive](data/2026-09-14-five-issues/evidence.tar.gz) retain requests, responses,
trajectories, baseline and final checks, patches, source hashes, independent
review receipts, and the unsuccessful attempts. Large source copies and model
weights are excluded; their public commits and archive hashes are recorded.
The model service's logs/state are a timestamped live capture, not a stopped-server postflight.

Verify the packet with:

```bash
python3 worker/collect_results.py --verify --out experiments/local-coding-worker/data/2026-09-14-five-issues
```

Prefill is input tokens divided by server prefill duration. HTTP time to first
token includes transport and scheduling. Decode here is the received-token
stream proxy, measured after the first token. Request input sizes grow during
a task; medians in the summary describe these particular sessions and must not
replace or be compared directly with the fixed 512-token prefill headline.
No fresh-server speed comparison or new quality/performance promotion was attempted.

## Remaining limits

Five selected issues are a first integration milestone. They do not establish
reliability on larger projects, untrusted repositories, long-running tasks,
network-dependent builds, or fresh-host installation. The first CPU image has
standard-library Python and Node; the optional PyYAML-dependent lab checker
was unavailable inside it and is not claimed as a passed worker check.

Independent review by separate Codex agents is recorded separately from the
local worker attempts and automatic test success. The local model produced
the candidate patches; the reviewers did not edit them.
Human review remains pending and patches are unmerged. The downloader patch's
new fixture has a nonblocking byte-count mismatch and needs CI wiring when
integrated. Preserve the original generated patch and its test receipt when
making later integration corrections.

The CLI patch meets the defined malformed-input cases. It also rejects
leading-zero and plus-prefixed representations, and does not bound very large
digit strings to finite safe integers. Review those integration choices before
merging; this trial does not establish universal numeric-input safety.
