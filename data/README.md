# Data Artifacts

This folder is a flat legacy archive of benchmark summaries, traces,
LocalMaxxing payloads/responses, and diagnostic output. Do not reorganize old
files by moving them; many notes and patch records link to exact paths.

Model-specific result packets should link to these files rather than duplicate
them. Start with [../results/README.md](../results/README.md) for promoted
packets and [../docs/model-effort-index.md](../docs/model-effort-index.md) for
the cross-model map.

## Consumer-ready experimental evidence

- [Qwen3.6 35B-A3B one-B70 concurrency sweep](qwen36-35b-autoround-b70-concurrency-20260824.json):
  measured raw-engine aggregate decode at 1-64 concurrent sequences, including
  the directly observed `1,039.408` tok/s seven-point profile and separate
  `1,052.870` tok/s B64 treatment. This is experimental speed evidence with an
  unresolved B64 repeat-identity gate, not a promoted package. Read the
  [scope guide](../docs/qwen36-35b-aggregate-throughput-evidence.md) before
  importing it.

## What To Track

Track compact artifacts that make a note reproducible:

- `*-summary-*.json`: benchmark identity, metrics, and quality result.
- `*-timing-decision-*.md` and `*-timing-decision-*.json`: routing artifacts
  used to choose the next target.
- Small `*.jsonl` traces when a note interprets a specific gate or state
  transition.
- LocalMaxxing payloads, responses, queue files, and submission logs that do
  not contain secrets.

Usually leave these local unless a note needs them:

- Full service `.log` files.
- `*-xpu-health.log` dumps.
- Repeated prompt/output JSON from every canary when the summary already
  records pass/fail and the failing answer.
- Large trace streams that are not cited by a note.

## Naming Pattern

For new Gemma 4 26B Q8 runs, prefer the existing run-directory shape produced
by `scripts/run-gemma4-26b-first-baseline.sh` /
`scripts/run-gemma4-26b-mtp-candidate.sh`:

```text
data/gemma4-q8-gpu<N>-<variant>-<stamp>/summary.json
data/gemma4-q8-gpu<N>-<variant>-<stamp>/chat-canary.json
data/gemma4-q8-gpu<N>-<variant>-<stamp>/p512o512.json
```

For new Qwen runs, prefer:

```text
qwen36-ablation-<label>-summary-<stamp>.json
qwen36-ablation-<label>-p<prompt>o<output>-<stamp>.json
qwen36-<purpose>-trace-<label>-<stamp>.jsonl
```

Keep the label stable across logs, summaries, and notes. If a run is invalid,
say why in the note instead of deleting the artifact.

## Staging Rule

In mixed experiment worktrees, stage explicit paths. Do not use broad
`git add -A` or `git add data/`.

Good default:

```bash
git add -- data/*summary-*.json notes/<date>-<topic>.md patches/<patch>.patch
```
