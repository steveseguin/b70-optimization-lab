# ctxkeeper 1.2.0 release checklist

## Current status after release review (2026-10-20)

**1.2.0 is already stable on GitHub and the public setup page.** Campaign 50's release gate passed;
the recovery checklist below is historical. Public assets were downloaded again during review and matched
all five entries in SHA256SUMS. The dedicated publishing repository is
[skindeepai/ctxkeeper](https://github.com/skindeepai/ctxkeeper), not the lab repository.

Its first PyPI attempt passed tests and built the package but failed with `invalid-publisher` because the
PyPI account has no matching trusted publisher. The package was not uploaded. The reviewed workflow now
validates the stable tag against package/code versions and source contents, tests the package, checks both
distributions with Twine, and verifies a clean wheel installation. A separate publishing job uses OIDC.
The source archive now includes the Dockerfile, example, tests and HISTORY. Runtime modules remain byte-identical
to the GitHub stable release; the immutable `v1.2.0` tag has not moved.

Pending publisher form values (GitHub tab):

| Field | Value |
| --- | --- |
| PyPI Project Name | `ctxkeeper` |
| Owner | `skindeepai` |
| Repository name | `ctxkeeper` |
| Workflow name | `workflow.yml` |
| Environment name | `pypi` |

The `pypi` GitHub environment already exists. The user adds the pending publisher in their PyPI account;
no token or password is needed. First run the workflow on `main` with `release_tag=v1.2.0` and `publish=false`
to validate. This passed at commit `a5f3bb7` in
[run 39532121058](https://github.com/skindeepai/ctxkeeper/actions/runs/39532121058): validation successful,
publication deliberately skipped. Stable source tests: 112 run, one skipped; strict Twine checks pass for
wheel and source archive; installed runtime hashes match the GitHub release. After the user confirms the form is saved, run:

```bash
gh workflow run workflow.yml --repo skindeepai/ctxkeeper --ref main -f release_tag=v1.2.0 -f publish=true
```

Verify the completed upload, install `ctxkeeper==1.2.0` from PyPI in a fresh environment and compare its runtime
module hashes with the stable release. Only then replace the live page's working GitHub-wheel installation
command with `pip install ctxkeeper`. A pre-existing local website draft already makes that replacement;
keep it unpublished until the PyPI check succeeds. Public page: <https://skindeep.ai/ctxkeeper.html>.

The lab's 1.2.2.dev0 bare-number checker is separate, experimental development. It is not part of this PyPI
release. Its unsupported offline efficacy estimate was removed; unit coverage does not establish a benchmark
improvement. Campaign 51 remains independent ongoing work; this review starts no new GPU campaign.

## Historical recovery checklist (superseded by the status above)

Recovered after the October 19 reboot. This file is durable; the earlier `/tmp` drafts were lost.
The owner prioritizes a usable public proxy: downloads, guide, model advice and honest test results.

## Verified so far

- Stable public release is 1.1.0. Working proxy is 1.2.0.dev10; package metadata now agrees.
- 112 local unit tests pass; `sync_notesdelta.py` confirms the harness copy matches. Fresh-venv pip installation reports the matching 1.2.0.dev10 version.
- c49b seed 0: 421/423, all forgery targets, 16/16 audits; all mechanism predictions independently pass.
- Seed 2 has no completed dev10 result. c49b was stopped and c49c was interrupted by the reboot.
- All 32 model-package manifests match the catalog; navigation now includes all 32.
- HISTORY.md is retained unchanged. Newer behavior belongs in README Changes.

## Remaining release work

1. Run the registered seed-2 stream with fresh state, dev10 and the same K32C flags. Retain interrupted runs.
   Use campaign37 runner, `LEAN_CLIENT=1`, `RESTORE=0`, `IDLE_MAX=0`, a fresh run label and seed-2-only queue.
   Never run builds or heavy repository checks beside the two-card server. Do not auto-retry failures.
2. Record final measurements and limits. Do not claim the two-seed bar until both completed runs support it.
3. Align code, package version, README, Docker example and public page for 1.2.0; preserve historical results.
4. Build a wheel and source archive containing Dockerfile, program files, demo, tests, README and LICENSE.
   Publish immutable checksums and standalone program/demo files. Keep build artifacts outside Git.
5. Install and test the built files in a fresh environment. Build Docker while cards are empty.
   Publish as a prerelease first so campaign 50 can test actual public download URLs before stable promotion.
6. Download public assets and verify checksums. Install wheel from the public URL; build Docker from the
   public source-archive URL. Record installed file hashes. Run campaign 50 G1-G4 exactly as registered:
   repair 40/40 fixed, >=38 clean, >=6/7 audit and <=45 min; Docker long-chat 300K 4/4; SDK plain/tool/stream;
   Gemma 100K smoke with --recipe agent --budget 15360 (report result, no quality gate). Leave cards empty.
7. Publish the GitHub stable release only after required checks; update release notes with actual results.
8. Update `/home/steve/skindeep/content/context-use.html`, run refresh_long_context then build_site;
   inspect desktop and phone; publish and fetch live page, download links, guide and evidence links.
9. Push focused verified commits on main. Check GitHub CI and deployed output. Keep incomplete model recipe
   qualifications explicit; no candidate becomes a starter without its clean-host replay.

## Boundaries

GitHub downloads and source-built Docker require no new account setup. PyPI and a prebuilt registry image
are optional distribution channels; do not make the usable public release depend on missing credentials.
Power settings, swap, caches and reboot are not part of this release. No resident server restoration.

## Repository-wide validation at recovery

All `run:` checks in `.github/workflows/guides.yml` were exercised locally (the PyYAML install step
was satisfied by the existing import). Three checks fail on pre-existing unrelated evidence:

- FP8 TP2 acceptance unit tests and acceptance collector: `compare-ladder-oracles.py` differs from
  the frozen packet and has no source-drift declaration. The current task did not modify that script.
- Whole-repository document audit: 550 new-to-baseline broken links in 95 documents, plus 4 known-broken.
  The focused public documentation link check passes.

All other guide checks pass, including recipe publication manifests, package/catalog validation,
manifest paths, historical pin checks, generated pages and container packet checks. Keep these
failures visible; they do not certify the affected frozen acceptance packet. Raw logs are retained
under `/home/steve/.cache/ctxkeeper-release-validation/`.

The undeclared FP8 comparator change is now resolved by a narrow whole-module AST proof and a drift
declaration, preserving frozen files and keeping current-source acceptance pending. Its 32 targeted tests
pass (one existing skip), the collector passes historical gates, and the historical pin check passes.
The 550-link research-history backlog remains; it is not hidden by a baseline update.

Stable download page published at https://skindeep.ai/context-use.html (website commit 0e3d81b).
All five 1.1.0 download assets match published SHA256SUMS; pip from the public wheel URL and Docker from
the public source URL both report 1.1.0. Desktop/phone layouts and local anchors pass; search vectors match
the new index. GitHub Pages deployment succeeded and the live page was fetched and checked.

## Public recipe-site deployment repaired (October 20)

The legacy neural.download Jekyll build failed on machine-specific symlinks in archived runtime packets.
The repository contains over 11 GB of tracked regular files, so copying the entire tree is not a viable fix.
`tools/stage-pages.py` now stages the static pages, copy-button targets, and linked evidence, including all
catalog/family manifest references. It preserves source bytes and refuses symlinks and missing required assets.
Historical Markdown and directory-link warnings remain in the uploaded inventory; no frozen files or link
baseline were rewritten. Missing model preview cards use the existing site card until their own image exists.

`publish-site` run 39367130246 succeeded for commit c674df916. The live catalog matches all 32 packages, a
downloaded guide README matches the source bytes, and the home page links directly to the proxy setup guide.
GitHub Pages now uses the checked-in Actions workflow. Stager tests: 10 passed; page-generator tests: 84 passed;
public doc links and all 6,607 manifest paths pass. The wider research-history link backlog remains separate.

The proxy guide's client environment, example variables, session IDs and estimated-context limits were also
corrected and deployed (skindeep commit ba13b33). Campaign 49d remains the only GPU workload.
