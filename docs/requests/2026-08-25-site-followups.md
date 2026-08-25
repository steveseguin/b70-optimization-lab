# Site follow-ups requested from the lab machine (2026-08-25)

Author: the site-side agent (ML Bottleneck / neural.download integration), on
Steve's instruction. These are the four items the site cannot complete from
outside the lab: they need pinned artifacts, hashes, launch flags, or
measurements that only exist on the lab hosts. Each item says what "done"
looks like so the site flips over automatically.

Status legend used below: `[ ]` open · `[x]` done · `[-]` declined with reason.

---

## 1. `[ ]` Two reproduction guides for Qwen3.6-35B-A3B

The family page (`models/qwen-35b.html`) is the only headline family whose
best results have **no install route**: its packet is a results README, so
the page's action is "Read the lab report" with the note "No step-by-step
install guide is published for this model yet." It is also the model behind
the site's best multi-user number (1,039 combined tok/s at 64 users), so the
gap is the most visible one on the site.

Please publish, per `docs/reproduction-guide-certification.md`:

| Guide | Route | Headline it must reproduce | Minimum classification |
| --- | --- | --- | --- |
| `repro/qwen36-35b-quark-int8-tp4-b70/README.md` | Quark W8A8 INT8, vLLM XPU, TP4, strict deep gate | 93.55 tok/s single user (`results/qwen36-35b-quark-int8-b70`) | `candidate-portable-repro` (`lab-replay` acceptable as a first cut, labeled) |
| `repro/qwen36-35b-autoround-int4-tp1-b70/README.md` | AutoRound W4A16 INT4 (`abhinand/Qwen3.6-35B-A3B-int4-AutoRound`), vLLM XPU, TP1, the r14/r16 stack | 90.91 tok/s single user **and** the 1..64-user aggregate sweep (`data/qwen36-35b-autoround-b70-concurrency-20260824.json`) | `research-status` is fine — but the guide must exist so the serving setup (graph captures at 1/32/64, batching harness, determinism caveat) is reproducible |

Each README needs the certification's dependency-closure table at the top
(host platform, toolchain, runtime commit/digest, patches with base commit +
checksum, model revision + checksums, checked-in config, execution commands,
validation gate + evidence path). Then:

- add both to `repro/guide-catalog.json` with honest `classification`,
  `components`, and `missing` lists;
- set `guide` on the matching packets in `families/qwen-35b.json` (the INT4
  lane currently has no packet at all — add one whose `featured_metric`
  points at `qwen35-autoround-tp1-single-r16`);
- run `tools/build-family-pages.py` and `tools/validate-repro-guides.py`.

**Done when:** `models/qwen-35b.html` renders "Open reproduction guide" as its
primary action and the INT4 packet card appears under "Packets and recipes".
No site-side change is needed; the generator keys off `guide`/`manifest`.

## 2. `[ ]` Sanitize machine-local paths in the publishing step

Published evidence JSON contains absolute lab paths, e.g.
`/home/steve/llm-optimizations/data/qwen36-abla...` inside
`data/qwen36-ablation-prefill-safe-int8-mixed-workspace-async-deep-gate-summary-20260615a13deep2.json`.
Published files are hash-pinned by other documents, so **do not rewrite
existing ones**. Instead, add a scrub to the packet/evidence publishing flow
so new files never carry them:

- rewrite `/home/<user>/...` and `/mnt/fast-ai/...` prefixes to repo-relative
  paths when the target is inside the repository, otherwise to a placeholder
  such as `<lab-workdir>/...`;
- keep a `path_sanitized: true` marker (or a note in the packet README) so
  readers know the transform happened;
- add the check to whatever validator gates a publish (a grep for
  `/home/` and `/mnt/fast-ai` over `data/`, `results/`, `repro/`,
  `packages/` for files newer than the rule's introduction).

**Done when:** the validator fails a publish that includes a machine-local
path, and the next published evidence file has none.

## 3. `[ ]` A *stock* multi-user sweep (no lab kernel stack)

The measured 1→64-user sweep is on the tuned r14 stack. ML Bottleneck can only
bound its stock projection with a tuned run ("stock ≤ tuned"); a plain-vLLM
sweep would let it check the scaling curve gain-for-gain (the engine test is
already written and self-activates when the row lands).

Please run the same harness with **stock vLLM XPU** (published nightly or the
`0.27.1` image, no lab patches, default graph settings), Qwen3.6-35B-A3B
AutoRound INT4, TP1, `i128/o1024`, temperature 0, two repeats, at
users = 1, 2, 4, 8, 16, 32, 64, recording per level:

```
{"users": N, "perUserTokS": x, "aggregateTokS": y}
```

Publish it beside the tuned sweep (e.g.
`data/qwen36-35b-autoround-b70-concurrency-stock-<date>.json`) with the same
`measurementProtocol` block and a `stack: "stock"` marker, and reference it
from `docs/qwen36-35b-aggregate-throughput-evidence.md`.

**Done when:** the JSON is on `main`. The site side then adds it to
`data/lab-evidence.json` as a `stock` concurrency row (ML Bottleneck repo),
which activates the gain-for-gain test and lets the multi-user report show
stock vs tuned as two measured curves.

## 4. `[ ]` Naming consistency note (no action unless you disagree)

The community MTP ladder (33.2 → 47.1 / 52.2 / 51.6 / 51.9) is filed here as
**Qwen3.8-27B** GPTQ INT4 (`community/field-reports/reddit-arc-b70-vllm-52tps`).
ML Bottleneck's evidence row previously said Qwen3.6-27B and has been
corrected to match this repo. If the field report is the one that is wrong,
say so in that report's STATUS and the site side will follow.

---

### How the site consumes these

- Family pages: `tools/build-family-pages.py` reads `guide`/`manifest` on each
  packet to choose between "Open reproduction guide" / "Open deployment
  packet" / "Read the lab report"; `featured_results` pins the hero.
- ML Bottleneck: `data/lab-evidence.json` rows (`stock` / `lab-baseline` /
  `tuned`) become the planner's "Nearest measured" and "Lab tuned" rungs and
  the `concurrencySweep` test in `tests/lab-evidence.test.mjs`.
