# MiniMax-H3: owner review before publication

Update, 2026-10-10: the owner approved Comfy-Org's published pruned BF16 denoiser, its source and the scheduling result. The lab analyzed that release; it did not produce the fit. Published input hashes are now verified on turin (two B70, 15 GiB RAM). See the [corrected guide](../../../repro/minimax-h3-pruned-bf16-tp2-b70-20261004/README.md) for the remaining baseline/reference, clean-build/runtime, independent full-suite repeat and public-release gaps. The native-video packet remains draft; the historical commands below do not establish publication certification.

Historical preparation follows. Prepared 2026-10-10. **No publication requested or performed by this change.**
Only this draft directory is in scope. The page, catalogs, generator and family
inputs remain unchanged. The owner's H3 decision is in
[AGENTS.md](../../../AGENTS.md), Lane Decisions (2026-09-19/20):
“Publish only after a confirmed significant improvement, and the owner reviews
first.” The later lossless-only rule also forbids a pruned model as the headline.
The [publication skill](../../../.agents/skills/publish-model-package/SKILL.md)
requires honest measurements and closed dependencies; it does not itself create
an extra approval requirement. This task explicitly stops at preparation.

## Decisions to record

| Owner decision | Concrete choice needed |
| --- | --- |
| What counts as significant? | Set a threshold and comparison: historical standalone-to-batch throughput, or matched fresh-process baseline/candidate batches. The recorded best is 396.625 s/clip versus 800.8 (2.019×); the later eight-clip improvement alone is 3.29%. Specify repeats, workload and whether the retained evidence suffices or a new matched campaign is required. |
| Which target and result may be published? | Select `duet-20261004T042838Z` as a clearly labelled historical **pruned BF16 + INT8 encoder research observation**, or require a new official/Unsloth target with new measurements. The current no-pruned-headline rule stays binding. Neither the 8-NFE runs nor the later two-clip transfer gate inherit the 50-NFE soak's headline. |
| Accept the picture and audio? | Review the exact selected clips for prompt following, motion, faces, temporal/tile seams, waveform quality and audio/video synchronization. Decide whether independent clips may be concatenated with visible/audible joins; no seamless continuation is established. Record the media hashes and the review. Byte equality alone cannot decide perceptual acceptance. |
| Weight source, license and redistribution? | Confirm the official license, derived-weight and runtime terms, required notices, and whether to link upstream downloads or redistribute permitted artifacts. The measured Comfy weights need written source justification and approval before any new download; the review-time revision is not yet matched to the measured files. |
| Publication level and wording? | Approve either a research/candidate listing with strict headline withheld, or a later fully qualified result after missing gates close. Approve the public wording and featured placement. Clean-host certification remains separate; no `starter` label without it. |

**Current answer: no publishable lossless headline; best recorded observation
396.6 s/clip, 2.02× the ledger's base schedule.** A significance/quality approval
does not manufacture missing model pins, baseline receipts, release assets or
fresh-process repeat evidence. Those are technical completion tasks.

## Work required before the commands below

1. Recover the historical model revisions/full hashes, standalone baseline pair,
   September eight-clip reference and complete timing/source logs. Bind the exact
   environment and source to the selected run. Review the 8-NFE/LoRA narrative
   discrepancy in [EVIDENCE.md](EVIDENCE.md). If inputs cannot be recovered, make
   new authorized measurements with a new identity; do not call them this run.
2. Complete a portable recipe: pinned weight download/verification, runtime
   build, all source deltas, rotation artifact/recovery inputs, finite launch,
   health, benchmark and graceful stop. Qualify any updated launcher separately.
   GPU work needs a separate authorized idle-host window; this task grants none.
3. Produce independent base-schedule quality/repeat evidence and a video-specific
   hash-bound promotion decision. Keep unsupported fields false. The
   [attestation standard](../../../docs/promotion-attestation.md) does not turn
   LLM token-suite booleans into video gates. A research listing keeps
   `library.featured_metric: null` and a nonempty `benchmark_status`.
4. Build from pristine public sources, publish permitted immutable release assets,
   download and hash every URL, and create the real
   `neural.download.recipe-publication.v2` manifest. Until then use `draft`.
   **The current validator hard-codes vLLM/XPU kernel fields and release kinds
   including `gdn-library`.** H3 is a native diffusers video pipeline. A reviewed
   video/non-vLLM schema extension is needed for truthful public certification;
   do not invent an H3 GDN library or insert dummy assets to pass it.
5. Prepare the approved payload described next. Use the
   [packet standard](../../../docs/neural-download-packet-standard.md),
   [recipe standard](../../../docs/recipe-publication-standard.md),
   [details checklist](../../../docs/details-page-checklist.md) and
   [complete LTX guide](../../../repro/ltx25-continuation-stream-b70-145f-20261010/README.md)
   as structural references. LTX results and acceptance do not transfer to H3.

No command can truthfully publish this draft today. The following is the exact
mechanical sequence **after** the owner decision and technical gates above,
not a claim that the missing payload already exists. It deliberately refuses
missing inputs and refuses a stale generator layout.

## Approved payload contract and validator enums

Proposed historical research package id:
`minimax-h3-pruned-bf16-tp2-b70-20261004`. A new official-weight result needs a new
id, source identity and editorial text. Future preparation should place these
reviewed files under `publication-draft/approved/` (none is created by this task):

- `repro/`: finished README, complete model/runtime manifests, measured JSON,
  original/reference evidence, attestation, verifier/build scripts and the real
  `publication-manifest.json`. Rewrite draft-relative links for the final repro
  location; do not copy this incomplete guide unchanged and remove its warning.
- `package.json`: `b70-model-package-v1`, matching id/guide, explicit two-card
  topology, actual model repository and recovered immutable revision, native
  runtime, all patch/dependency paths, contributor credit at its exact scope,
  and commands with exactly `preflight`, `launch`, `health`, `benchmark`, `stop`.
- `guide-entry.json`: matching guide-catalog entry and package path, component
  booleans reflecting actual closure, declared dependency links and missing gates.
- `owner-decision.json`: dated reviewed record, with `approved: true`, the package
  id and written significance, target/result, media-quality and license decisions.
- `featured-observation.json`: **only for this historical research selection**,
  `run_name: "duet-20261004T042838Z"`, `wall_seconds: 3173`, `clips: 8`, and
  `evidence: "experiments/minimax-h3-b70/data/2026-10-04-soak8/session.log"`.
  Recompute it from the retained log and receipts; it is a scoped observation.

Enums read from `tools/validate-repro-guides.py`:

- Guide classification: `starter-guide`, `candidate-portable-repro`, `lab-replay`,
  `record-capsule`, `research-status`, `archived`.
- Audience: `beginner`, `intermediate`, `expert`, `researcher`, `historical`.
- Package status: `candidate`, `starter`, `preview`. **`draft` is not a package
  status**; publication-manifest status is separately `draft` or `published`.
- Component keys: `platform_install`, `model_download`, `source_restore`, `build`,
  `launch`, `validation`, `patch_links`, `hashes`, all booleans.
- OS: `Linux`/`Windows`; delivery: `native`/`container`; contributor kind:
  `lab`/`external`; status: `acknowledged`, `credited`, `validated-boost`, `integrated`.
- Token performance profiles allow `decode`, `prefill`, `ttft`, `aggregate_decode`.
  Do not force video into those. Use `video_measurements`, modalities `video` and
  `audio`, with clear scope and evidence per row. If retaining 396.625 as a
  `period_seconds` observation, label it **whole-batch wall / 8 clips, not observed
  delivery cadence**; `new_video_seconds=124/24`; `samples=8` clips in one batch.

A reviewed research listing would use `status: candidate`, expert/researcher
classification, `clean_host_tested: false`, and explicit missing gates. Public
source closure does not by itself qualify a performance headline. Keep 396.6
outside the strict featured-metric slot unless a later applicable gate clears it.

## Exact registration commands — only after approval and completion

Run from the repository root on `main`. All CPU commands run at nice 19 with
`OMP_NUM_THREADS=2`. No server, unit or endpoint is part of this sequence.

```bash
export OMP_NUM_THREADS=2
export PYTHONDONTWRITEBYTECODE=1
test "$(nice -n 19 git branch --show-current)" = main
nice -n 19 git fetch origin main
nice -n 19 git diff --stat HEAD..origin/main
# Inspect the preceding stat for unexpected deletion before proceeding.
nice -n 19 git pull --rebase origin main
nice -n 19 python3 -B - <<'REGISTER'
import json, shutil
from pathlib import Path
root = Path('.')
draft = root / 'experiments/minimax-h3-b70/publication-draft/approved'
pid = 'minimax-h3-pruned-bf16-tp2-b70-20261004'
decision = json.loads((draft / 'owner-decision.json').read_text())
assert decision['approved'] is True and decision['package_id'] == pid
package = json.loads((draft / 'package.json').read_text())
entry = json.loads((draft / 'guide-entry.json').read_text())
manifest = json.loads((draft / 'repro/publication-manifest.json').read_text())
assert package['id'] == entry['id'] == pid
assert package['guide'] == entry['guide'] == f'repro/{pid}/README.md'
assert entry['package'] == f'packages/{pid}/package.json'
assert package['library']['featured_metric'] is None
assert manifest['publication_status'] == 'published'  # only after real closure
assert manifest['guide'] == package['guide']
assert not (root / 'repro' / pid).exists()
assert not (root / 'packages' / pid).exists()
catalog_path = root / 'repro/guide-catalog.json'
catalog = json.loads(catalog_path.read_text())
assert not any(e['id'] == pid for e in catalog['guides'])
shutil.copytree(draft / 'repro', root / 'repro' / pid)
(root / 'packages' / pid).mkdir()
shutil.copy2(draft / 'package.json', root / 'packages' / pid / 'package.json')
shutil.copy2(draft / 'featured-observation.json',
             root / 'repro' / pid / 'featured-observation.json')
catalog['guides'].append(entry)
catalog_path.write_text(json.dumps(catalog, indent=2) + '\n')
REGISTER
```

The approved package dependency list must include the copied observation and
all required files. Stage every new dependency explicitly before validation:
the validators check Git tracking. Do not invent a model revision to satisfy the
40-character revision check. `packages/catalog.json` is generated, never manually
patched. A package alone does **not** enter featured picks: selection is explicit
inside `tools/featured_picks.py::groups()`.

## Exact featured-picks change for the approved research selection

This CPU edit is future command text, not executed by this task. It adds a
separate two-card video role, retains LTX, uses its own video units and removes
the now-stale “no package” sentence. The observation remains separate from a
strict metric, following the existing video-card convention.

```bash
nice -n 19 python3 -B - <<'FEATURE'
from pathlib import Path
p = Path('tools/featured_picks.py')
s = p.read_text()
anchor = '    # One editorial role per featured setup; scores never clear quality gates.\n'
addition = """    h3 = pick('minimax-h3-pruned-bf16-tp2-b70-20261004',
        'MiniMax-H3 · video with audio on two cards',
        'Research observation · pruned target; strict headline withheld',
        'Independent clips with stereo sound. Scheduling changes preserve the tested '
        'local reference; equality to the full official model is not established.', research=True)
    h3_path = 'repro/minimax-h3-pruned-bf16-tp2-b70-20261004/featured-observation.json'
    h3_run = read(h3_path)
    assert h3_run['run_name'] == 'duet-20261004T042838Z'
    assert h3_run['wall_seconds'] == 3173 and h3_run['clips'] == 8
    h3['observation'] = (f"{h3_run['wall_seconds']/h3_run['clips']:.1f} seconds per clip (batch average)",
                         h3_run['evidence'])
    h3['note'] = ('One eight-clip batch; 124 frames at 960×544 per clip. '
                  '24 fps is playback speed, not generation speed. '
                  'Pruned BF16 denoiser and INT8 encoder; full official-target parity remains unproven.')
"""
replacements = {
 anchor: addition + anchor,
 'featured = [int4, gemma, fp8, laguna, shared, flash, video]':
 'featured = [int4, gemma, fp8, laguna, shared, flash, video, h3]',
 "'Continuing video with audio']":
 "'Continuing video with audio', 'Independent video clips with audio on two cards']",
 "and pick['id'] != 'ltx25-continuation-stream-b70-145f-20261010':":
 "and pick['id'] not in {'ltx25-continuation-stream-b70-145f-20261010', 'minimax-h3-pruned-bf16-tp2-b70-20261004'}:",
 '<strong>2 cards:</strong> Qwen 27B shared chat.':
 '<strong>2 cards:</strong> Qwen 27B shared chat; MiniMax-H3 video research.',
 'but no published site package yet.':
 'and an owner-reviewed research package; its strict headline remains withheld.',
}
for old, new in replacements.items():
    assert s.count(old) == 1, ('Generator changed; review the edit again', old)
    s = s.replace(old, new, 1)
p.write_text(s)
FEATURE
```

Review/update the editorial ranking note, `packages/README.md`, top README and
CURRENT in the publication commit to state the actual approval and classification.
If the owner chooses a new official-weight result instead, do not run this
historical-pruned-result edit unchanged. Public detail pages need explicit gaps
for unmeasured prompt reading, scaling, quality and projections. No video token
bars, invented curves or seamless-stream promises.

## Generate, validate, release and verify

These commands are for that later approved publication. They are intentionally
not run as part of this draft. Required release upload/download verification
comes before `publication_status: published`; actual asset filenames and URLs
must come from the completed build, so no fabricated upload command is supplied.
Record `remote_verified_at` only after every public asset is fetched and hashed.

```bash
nice -n 19 git add -- \
  repro/minimax-h3-pruned-bf16-tp2-b70-20261004 \
  packages/minimax-h3-pruned-bf16-tp2-b70-20261004/package.json \
  repro/guide-catalog.json tools/featured_picks.py
nice -n 19 python3 -B tools/validate-recipe-publication.py \
  repro/minimax-h3-pruned-bf16-tp2-b70-20261004/publication-manifest.json
nice -n 19 python3 -B tools/validate-recipe-publication.py --check-remote \
  repro/minimax-h3-pruned-bf16-tp2-b70-20261004/publication-manifest.json
nice -n 19 python3 -B tools/validate-repro-guides.py --write-package-catalog
nice -n 19 python3 -B tools/build-family-pages.py
nice -n 19 python3 -B tools/build-model-pages.py
nice -n 19 python3 -B tools/sync-public-result-summary.py
nice -n 19 python3 -B tools/validate-repro-guides.py
nice -n 19 python3 -B tools/check-doc-links.py
nice -n 19 python3 -B tools/check-manifest-paths.py
nice -n 19 python3 -B -m unittest tools/test_validate_repro_guides.py \
  tools/test_validate_recipe_publication.py tools/test_build_model_pages.py \
  tools/test_build_family_pages.py tools/test_measured_opt_contract.py
nice -n 19 git diff --check
nice -n 19 git diff --stat
```

Inspect generated files and rendered pages at narrow/wide widths and without
JavaScript; verify links and video scopes. Stage newly generated model/index/site
pages and changed summary/docs with explicit paths, plus every dependency and
any validator/schema changes from the reviewed closure work. No broad `git add -A`.
Then, after all checks pass:

```bash
nice -n 19 git commit -m 'Publish owner-reviewed MiniMax-H3 research package' \
  -m 'Co-Authored-By: Codex <noreply@openai.com>'
nice -n 19 git fetch origin main
nice -n 19 git diff --stat HEAD..origin/main
# Inspect incoming changes and preserve the other host work.
nice -n 19 git pull --rebase origin main
# Re-run affected validation if the rebase changes inputs, then:
nice -n 19 git push origin main
```

Watch guides/package CI and Pages deployment for that commit. Fetch the live
`https://neural.download/packages/catalog.json`,
`https://neural.download/models/minimax-h3-pruned-bf16-tp2-b70-20261004.html` and
home page with a cache-busting query; confirm the correct commit's new package,
its featured card, withheld strict headline, evidence links and video scope.
A successful push is not proof of live deployment. None of these publication
or site-generation actions is authorized by the current drafting task.
