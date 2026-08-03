# Laguna INT4 accuracy evaluation preregistration

Date: 2026-08-03 America/Toronto

Status: **preregistration plus the harness source it defines; host-tested only.
No model was loaded, no endpoint was contacted, no XPU work was performed, and
nothing was measured. No accuracy number exists yet and none is claimed here.**

## The gap this closes

The campaign's evidence standard for *change* is very strong: frozen oracles,
bit-identical output token IDs, `cached_tokens=0`, four-rank selector records,
grouped-GEMM DSO inode and hash proofs. The evidence standard for *quality* is
that there is none.

This was verified rather than assumed. Immediately before this work, across the
whole `experiments/laguna-s-2.1-xpu-b70/` tree at `ae7045d61`, there was not one
occurrence of `mmlu`, `humaneval`, `mbpp`, `gsm8k`, `pass@`, `exact_match`, or
`accuracy` in any `.py`, `.md`, `.sh`, or `.json` file. The only quality
vocabulary present was `needle` / `haystack` / `retrieval`. What existed was:

| artifact | what it actually checks |
| :--- | :--- |
| `bench_laguna_long_context.py` | a synthetic needle-in-haystack JSON object with five fields, plus `cached_tokens=0` and counter consistency |
| repeat/teacher oracles | the model reproduces *its own* previous token IDs |
| `realistic-suite-v1.json` | 13 coding-flavoured prompts with **no answer keys**; `bench-openai-realistic-suite.py`'s `passed` is a cache-zero freshness gate, not a correctness gate |
| `run_laguna_production_readiness_canary.sh` | one 400-token request matched against the canonical q1 prefix -- again self-consistency |

Repo-wide the closest prior art is the DeepSeek V4 lane's `quality/` directory,
which is a different model and which states of itself: *"It is not yet an
executable scoring suite... No intelligence or promotion decision may use v1
alone."* Its `calibration-v1-plan.json` names GSM8K, MMLU and APPS, but as a
frozen expert-pruning calibration plan whose prompt JSONL was never
materialized. There is no executable accuracy scorer anywhere in this
repository, for any model.

The consequence is precise and worth stating plainly. Every quality gate the
Laguna lane owns compares the INT4 model against itself. INT4 quantization, the
offline Hadamard rotation, and TP4/EP4 sharding are all baked into the oracle,
so no existing gate can detect that any of them damaged the model. Every kernel
optimization to date is unfalsifiable on quality, and the model cannot be put in
front of users on this evidence.

## What the model is

Established from campaign notes that recorded direct inspection of the pinned
checkpoint, plus a hard runtime guard in the fork
(`vllm/model_executor/models/laguna.py:230-246`) that asserts exact config
values. The checkpoint itself lives under `/mnt/fast-ai` and is inside the
quarantine, so it was not read for this note.

* 48 layers: layer 0 dense, 47 MoE. Hidden size 3,072, vocabulary 100,352.
* 256 routed experts, top-10, ungrouped **sigmoid** routing, `norm_topk_prob`,
  routed scaling factor 2.5, one shared expert of width 1,024. 64 local experts
  per EP4 rank.
* 12 full-attention layers (48 Q heads) and 36 sliding-attention layers (72 Q
  heads), 8 KV heads throughout, head dimension 128, sliding window 512.
* Full attention: YaRN, theta 500,000, rotary dimension 64 of 128. Sliding
  attention: theta 10,000, rotary dimension 128.
* Served at `max_model_len=32768`, TP4/EP4, BF16 KV cache, block size 64,
  `max_num_seqs=1`, prefix caching off.

Two facts about the quantization matter for eval design:

**The INT4 is confined to the routed experts.** The checkpoint contains 36,096
I32 packed weights and 36,096 BF16 scales -- exactly `47 MoE layers x 256
experts x 3 projections` -- as symmetric group-32 W4A16. Attention, the shared
expert, dense layer 0, the embeddings and the LM head are **BF16**. Whatever
damage quantization did is concentrated in the routed-expert path, which is the
path that top-10-of-256 routing makes input-dependent. That is an argument for
breadth of prompt distribution over depth on any single task.

**The Hadamard transform is offline.** The config declares `weight_input` /
`weight_output` rotations and the loader instantiates zero runtime Hadamard
modules, so the rotation is a property of the stored weights and not a runtime
cost or a runtime risk.

Parameter count: not stated anywhere in this repository. The safetensors index
declares 71,898,444,992 payload bytes and 72,961 tensors, and vLLM reported
16.92 GiB of weights per card. The published F16 GGUF is 235,202,258,240 bytes,
which at two bytes per parameter puts total parameters near 117 B, with roughly
9 B active per token. **Both figures are arithmetic, not quoted values**, and
neither should be cited as authoritative. The "70B" in the campaign's shorthand
tracks the ~70 GiB INT4 artifact size, not a parameter count.

## The BF16 reference does not exist and cannot exist here

The highest-value comparison available in principle is INT4 against a BF16 copy
of the same checkpoint, which would attribute quality loss to quantization
specifically. It is not available:

* only two Laguna model directories have ever existed on this host,
  `/mnt/fast-ai/llm-models/laguna-s-2.1/int4` and `.../dflash-int4`
  (100 files / 72,021,173,058 bytes and 18 files / 2,229,975,225 bytes). The
  directory named `dflash-int4` holds BF16 weights, but it is the 2.2 GB
  six-layer **draft**, not a BF16 target;
* no Laguna model directory exists anywhere else on local disk. The HF hub cache
  entries for `poolside/Laguna-S-2.1-INT4` and `...-DFlash` are 12 KB of refs
  with no blobs;
* the BF16 repository is about 219 GiB. The root filesystem has 75,313,512,448
  bytes free, and four B70s hold roughly 128 GiB of VRAM in total. A BF16 target
  cannot be stored here and could not be served TP4 if it were.

So the quantization-cost question is **not decidable on this hardware**, and the
harness does not pretend otherwise. What it can do instead is establish the
INT4 model's absolute quality, and thereafter detect any change to it exactly.
Published model-card numbers may be cited as a loose sanity cross-check but are
not a control: they were produced on different hardware, a different runtime, a
different prompt format and a different scorer.

## Determinism is the design premise, not an assumption

The serving configuration is greedy end to end: `temperature=0`, `top_p=1`,
`draft_sample_method=greedy`, `rejection_sample_method=standard`. Reading the
fork's `vllm/v1/sample/rejection_sampler.py`, the greedy path computes
`target_argmax = target_logits.argmax(dim=-1)` and then, in
`rejection_greedy_sample_kernel` with `SYNTHETIC_MODE` off, stores

```python
token_id = target_argmax_id
rejected = draft_token_id != target_argmax_id
```

The emitted token is **unconditionally the target's argmax**; the draft token is
compared only to decide where the accepted run stops. Speculation changes speed
and not output, and draft depth, acceptance rate and draft quality cannot move a
single output token.

This is specific to `rejection_sample_method="standard"`. The `synthetic` branch
of the same kernel stores `draft_token_id if accepted else target_argmax_id`
where acceptance is drawn against a uniform probability -- genuinely random, and
not argmax-equal. The harness refuses to score any configuration whose
speculative sampling is not greedy/standard, because outside that setting exact
comparison is simply not valid.

With prompts pinned as token-ID arrays, the entire response is therefore a pure
function of weights, kernels, batch shapes and the prefill partition. That makes
quality-regression detection *exact*: a single changed answer is signal, not
noise. It is a far stronger instrument than the usual "within the confidence
interval" comparison, and it is what makes an 80-item suite worth running at
all.

Determinism has four known ways to break here. Each has an explicit check, and a
check that cannot be evaluated is a refusal, not a pass.

1. **Prefill partition.** Measured in this campaign on 2026-08-02: moving the
   32,640-token partition from `8182+8182+8182+8094` to `8192+8192+8192+8064`
   changed output token IDs on all eight long rows, first mismatches at indices
   67-91. The harness reads the resolved batched budget and the derived
   scheduled budget out of vLLM's own logging via
   `assert_laguna_resolved_cache_partition.analyze` and refuses if either
   differs from the contract. The regression gate additionally refuses to
   compare two runs whose resolved partitions differ at all.
2. **Batch co-residency.** Two in-flight requests change the verifier width and
   therefore the MoE and GEMM reduction order. The contract must declare
   `max_num_seqs=1`; requests are sent strictly serially; and every request must
   move `vllm:request_prefill_time_seconds_count` and
   `vllm:request_decode_time_seconds_count` by exactly one, which is what proves
   nothing else shared the step.
3. **Prefix caching.** A shared prompt prefix would both warm the run and change
   numerics. `enable_prefix_caching` must resolve `False` in the server log and
   every row must report `cached_tokens == 0`.
4. **Everything else.** Not argued, measured. With `--replicates 2` the whole
   suite is sent twice, as two full passes rather than adjacent repeats, so
   order- and state-dependent drift is in scope. Every item's output token IDs
   must be identical across passes. A run that cannot reproduce itself is marked
   `PASS_SCORED_DETERMINISM_UNVERIFIED` and the regression gate refuses to use
   it as an oracle.

One boundary the harness states rather than hides: a speculation-on run and a
speculation-off run are **not** expected to be token-identical, even though
greedy rejection is output-lossless. The target logits are computed at verifier
width 12 in one case and width 1 in the other, so the tiling and reduction order
differ and a near-tie argmax can flip. Those two configurations may be compared
on score, never on exactness.

## The suite, and what was rejected

The intended production use is a **coding agent**. The suite is chosen for that,
in two phases.

### Phase A -- exact-match, no code execution

**GSM8K exact-match, 80 items.** Multi-step arithmetic is where quantization
damage shows up earliest and most cheaply: a long dependent chain has no slack,
so a single degraded routed-expert decision propagates. It is also the only real
benchmark whose data is already on this host. Scored by a frozen extraction
rule, and the prompt explicitly demands the `#### <number>` format the rule
reads first.

**A coding-agent output-format contract.** The failure mode that breaks a coding
agent in production is not usually a wrong algorithm; it is a malformed tool
call, a broken diff, an invented path. That is mechanically checkable with zero
external data and zero code execution. It is included as a *format* adapter with
an exact-field JSON scorer, deliberately kept small, and labelled in the code as
having **no external validity** as an intelligence measure -- it is a regression
and integration signal only. Writing one's own benchmark and reporting it as a
quality number would recreate exactly the unfalsifiability this note exists to
end.

**MMLU multiple-choice, pluggable.** Included because it is the conventional
quantization-damage number and the adapter is small. It is explicitly *not*
recommended as a coding-agent gate, and the registry entry says so.

### Phase B -- functional coding correctness, code execution

**HumanEval pass@1, 164 items**, and optionally **MBPP sanitized**. This is the
single most relevant number for a coding agent and the suite is not complete
without it. It is Phase B only because the data is not on this host, not because
the capability is missing: the sandbox is built, and tested, now.

### Rejected

* **Perplexity on a held-out corpus.** Cheap and sensitive, and it needs no
  scorer -- but this endpoint is a chat completions service and per-token
  logprobs over a corpus are a different access pattern. More importantly,
  perplexity does not answer "can it code", and a perplexity delta is not
  something a promotion decision can be reasoned about.
* **An LLM judge.** Non-deterministic, unauditable, and it would import a second
  model's opinions into a campaign built on exactness.
* **Full-size MMLU (14,042 rows).** The runtime cost is not justified for a
  coding agent, and a small random subsample has poor power while inviting the
  reader to treat it as the real MMLU number.
* **A large self-authored quality suite.** No external validity, and it would
  let the harness grade its own homework.
* **Sampling at temperature > 0 with n>1 for pass@k.** It would destroy the
  determinism that makes exact regression detection possible, in exchange for a
  metric nobody here needs.

### Sample size honesty

At n=80 and p≈0.5 the Wilson 95% interval is roughly ±11 points; the gate
reports the interval on every dataset for exactly this reason. **A suite this
small cannot license a promotion on score.** It can do two things well: give a
first absolute reading of INT4 quality, and detect any change exactly. The gate
below is built around that division and does not overreach.

## Dataset availability, audited

Measured on this host on 2026-08-03. Sizes given are bytes actually observed;
sizes not observed are not asserted.

| dataset | status | bytes | usable for |
| :--- | :--- | ---: | :--- |
| `/home/steve/src/AngelSlim/dataset/gsm8k/question.jsonl` | **present**, 80 rows, all with `#### <answer>` | 48,188 | GSM8K exact-match |
| `/home/steve/src/AngelSlim/dataset/humaneval/question.jsonl` | **present**, 80 rows | 63,176 | prompts and exact regression only |
| HumanEval with tests | **absent** | not measured | required for pass@1 |
| MBPP | **absent** | not measured | required for pass@1 |
| MMLU | **absent** | not measured | required for the knowledge canary |

Two findings carry consequences.

The locally available HumanEval sample **cannot produce a pass@1 score**. Its
rows carry `question_id`, `turns`, `reference` and `category` -- there is no
`test` field and no `entry_point`, so functional correctness is not computable
from it. The adapter refuses such a file by name rather than substituting a
similarity metric, and a test asserts that refusal.

The GSM8K sample's provenance is incomplete. The vendor does not declare which
split these 80 rows came from or how they were selected. It is a usable
regression and first-reading instrument; it is **not** a GSM8K test-split score
and the registry entry forbids reporting it as one. Provisioning the official
1,319-row test split would fix this and is the recommended first upgrade.

`datasets` is installed in the pinned venv; `lm_eval`, `human_eval` and
`evaluate` are not, and the harness depends on none of them.

## Code execution: sandboxed now, phased on

The brief's choice was to sandbox properly or to defer. The answer taken here is
both, in the order that makes each honest.

The sandbox is **built and adversarially tested now**, because a deferred
sandbox is a sandbox that never gets written, and because every test it needs is
a Python snippet this repository can author -- no model, no data, no device.
`eval_laguna_sandbox.py` runs each program in a fresh session (`setsid`) under
`RLIMIT_CPU`, `RLIMIT_AS`, `RLIMIT_NPROC`, `RLIMIT_FSIZE` and `RLIMIT_CORE=0`,
with a wall-clock timeout followed by `SIGKILL` to the whole process group, a
scrubbed environment, `python -I`, and a throwaway directory that is also `HOME`
and `TMPDIR`. Verified behaviours, each with a test: a hang is killed; a CPU burn
is killed by the CPU limit before the wall clock; runaway allocation fails;
network access is denied; process creation is capped but not forbidden; an
output flood is bounded and flagged; `stdin` is closed; the working directory is
removed.

The boundary is stated in the module for what it is: **robustness, not
security**. There is no filesystem namespace, so a program can read whatever
this user can read, and the socket-neutering preamble runs in the same
interpreter as the code it restricts. That is adequate against what a language
model actually emits and inadequate against a deliberate attacker. A real
boundary needs `unshare -n -r`; it is supported behind a flag, and
:func:`probe_network_namespace` decides at runtime rather than assuming. Probed
on 2026-08-03 it **failed** with `write failed /proc/self/uid_map: Operation not
permitted` -- but that probe ran inside the agent's own restricted shell, so
whether it works in an unrestricted login shell on this host is **not
established**. When the namespace is requested and unavailable the sandbox
returns `REFUSED`; it never silently degrades.

Execution is nevertheless **default-off**. `eval_laguna_accuracy` refuses any
code-execution item unless `--enable-code-execution` is passed, and importing
the dataset module cannot reach the code-exec scorer at all. Phase A therefore
runs with no untrusted execution on a host that holds weeks of campaign evidence
and a 72 GB checkpoint, and Phase B needs one flag plus one provisioned dataset.

## Attribution

A score is meaningless unless it is attributable to an exact configuration.
Nothing is taken from the launcher's argv. Every scoring run binds:

* the **resolved selector set** from the four per-rank worker records the fork
  prints, validated against the frozen contract hash by the existing
  `validate_laguna_worker_selector_evidence.parse_worker_selector_log`;
* the **resolved cache and partition settings** from vLLM's own logging via
  `assert_laguna_resolved_cache_partition.analyze`;
* the **grouped-GEMM DSO** path, device, inode and SHA-256, consumed from the
  evidence JSONL that the existing validator already writes, and required to be
  identical across all four ranks and equal to the contract;
* the **vLLM and XPU-kernels commits**, compared against the contract;
* the **checkpoint identity**: served model name, target and draft revisions,
  and SHA-256 of `config.json`, `tokenizer.json`, `tokenizer_config.json`,
  `chat_template.jinja`, `special_tokens_map.json` and
  `generation_config.json`;
* the **data and logic identity**: dataset file hash, item-id set hash, prompt
  hash set, the SHA-256 of the scorer module, the SHA-256 of the sandbox module,
  and the hash of every frozen prompt template;
* the **per-item prompt token-ID array hash**, so a prompt hash means one exact
  array and not one string that two tokenizers might disagree about.

The harness reuses the campaign's existing evidence tools rather than
reimplementing them, so a selector contract change breaks the accuracy gate at
the same moment it breaks everything else.

## The regression threshold

**Gate E, exactness, primary.** Every item's output token IDs must equal the
frozen accuracy oracle's. If they all do, the candidate is output-identical and
its quality is *proved* equal by construction -- the oracle's scores transfer
without re-measurement, and quality does not block the promotion. Verdict
`PASS_OUTPUT_IDENTICAL`. This is what makes the gate affordable: an
output-neutral kernel does not have to re-run the suite to be cleared.

**Gate S, score, consulted only when Gate E fails.** Once outputs differ the
candidate is a different machine.

* Any per-dataset accuracy **below** the oracle's -- not "outside the interval",
  below, by one item -- blocks promotion. Verdict `BLOCK_SCORE_REGRESSION`. At
  n=80 an interval test would accept a real quality loss, and the campaign
  standard is that quality is never traded for speed.
* Equal or higher scores with changed outputs is `REVIEW_OUTPUT_CHANGED`, which
  **authorizes nothing automatically**. A human must enumerate the changed items
  in a note and decide. A score improvement at this sample size is far more
  likely to be a bug than an improvement, and is treated the same way.
* A changed denominator is treated as a regression, because it means items
  became unscoreable.

**Refusals.** The gate refuses to compare at all if the scorer revision, prompt
templates, dataset hashes, item set, per-item prompt arrays, sampling
parameters, or resolved partition differ, or if the oracle's determinism was
never proved. Selector sets and DSO hashes are deliberately *not* comparability
requirements -- those are exactly what a kernel candidate is supposed to change.

**Unscoreable items are never skipped.** An item with no extractable answer, a
response truncated at `max_tokens`, or a scorer that is not enabled counts as
**incorrect** and is separately reported in `unscoreable` and `truncated`
counts. Any refusal at all makes the whole run `REFUSED` with exit code 2.

### How this composes with bit-exactness

They are complementary and neither substitutes for the other.

* The existing repeat-oracle gates prove **unchanged** on the benchmark prompts.
  They say nothing about whether the unchanged behaviour is any good, because
  the oracle came from the same quantized model.
* This gate proves **good enough**, and its Gate E reuses the same evidence type
  -- output token-ID equality -- so an output-neutral kernel passes both for the
  same underlying reason.

A promotion needs both: bit-exactness against the benchmark oracle, and either
Gate E against the accuracy oracle or an explicit recorded human decision after
Gate S. Bit-exactness alone can promote a fast kernel attached to a broken
model. Accuracy alone can miss a kernel that is correct on 80 prompts and wrong
elsewhere. The pair is the useful object; either alone is not.

## What a pass does and does not authorize

A `PASS_SCORED` run authorizes exactly one thing: a written statement of the
INT4 model's accuracy on the named suites, at the named resolved configuration,
with the recorded attribution.

A `PASS_OUTPUT_IDENTICAL` verdict authorizes exactly one thing: the statement
that quality does not block that specific candidate's promotion.

Neither authorizes:

* any claim about quantization cost, which requires a BF16 reference that does
  not exist on this host;
* any claim that the model is fit for production users -- a coding agent's
  fitness is not established by 80 arithmetic problems and a format check;
* any throughput, latency, promotion, submission, or LocalMaxxing claim of any
  kind. The harness measures no timing and deliberately runs with
  `ignore_eos=False`, which makes its requests unsuitable for a decode
  measurement;
* reporting the 80-row GSM8K sample as a GSM8K test-split score, or the
  self-authored format suite as an intelligence measure;
* extending a score across a partition change, a selector-profile change, a
  prompt-template change, or a scorer change. Each of those mints a new oracle.

## Validation

Host only, in this repository. No network, no model, no device, and the only
code executed under the sandbox was written by the test file itself.

* **131 new CPU-only tests pass**: 45 for the dataset adapters and scorers, 20
  adversarial tests for the sandbox, 40 for the harness, 26 for the regression
  gate.
* The sandbox tests are behavioural, not structural: they start real
  subprocesses and assert that a hang is killed, a CPU burn is killed by the CPU
  limit, allocation fails, network is denied, forks are capped, output floods
  are bounded and flagged, `stdin` is closed, a missing interpreter is
  `REFUSED`, and the working directory is removed afterwards.
* The dataset tests run against the real AngelSlim GSM8K file on this host and
  assert 80 items, 48,188 bytes and a stable provenance hash; they skip cleanly
  if the file is absent.
* Two defects were found by these tests during development and fixed: the
  duplicate-item-id check ran after the row-count check and so was masked by a
  less specific message, and `RLIMIT_NPROC` was sized from a process count
  rather than a task count, which on this 89-task host set a limit low enough to
  block the first `fork` of a legitimate program.
* Ruff: `ruff check` passes on all eight new files and all eight are
  `ruff format` clean. Baseline for comparison, measured with these files
  excluded: the pre-existing tools directory reports **17** `ruff check`
  findings, none of them in these files, and at least one existing tool
  (`compare_exact_runs.py`) is not `ruff format` clean. So the repository is not
  uniformly formatted, but the dominant convention is formatted, and these files
  follow it.
* Full lab suite before and after: **4 failed, 780 passed, 168 subtests** before
  and **4 failed, 964 passed, 168 subtests** after. The same four pre-existing
  failures, none touched here.

  The +184 does **not** all belong to this work, and the difference is worth
  recording rather than glossing. `pytest --collect-only` attributes exactly
  **131** collected cases to `test_eval_laguna_*.py`. The remaining **53** come
  from `test_serve_laguna_production.py`, a file added concurrently by a sibling
  agent working in this same tree during this session, alongside
  `serve_laguna_production.sh` and
  `notes/2026-08-03-production-concurrency-audit.md`. None of those three files
  was read or modified here, and none of this work depends on them.

## Boundary

The corrected-error PCIe/NVMe quarantine remains controlling. This note and its
source authorize no model load, service start, endpoint contact, XPU probe,
benchmark, swap change, reset, reboot, or recovery action. No execution lock,
runtime lock, evidence packet, or frozen manifest was created, refreshed, or
modified. The checkpoint under `/mnt/fast-ai` was not read.

No accuracy number has been produced. The harness is inert until a human
authorizes a device window and supplies a preregistered contract.

The protected `125.4619731637751 tok/s` conventional short-decode record is
untouched by this preregistration and by any run it authorizes. This harness
measures accuracy, not throughput; it does not run, rescore, or supersede that
record, and no result from it may be compared against that number.
