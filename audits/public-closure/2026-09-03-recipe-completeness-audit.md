# Recipe completeness audit, 2026-09-03 (four-B70 host)

Read-only audit of every `repro/` guide, `index.html`, `README.md`, `models/*.html`, run by a Claude subagent on 2026-09-03 at `a16cb3880`. Outcome: the two blocking items and the degrades below were fixed the same morning in commits `66a54613e` (catalog, package dependency, banners, script overrides, R62 note, sitemap) and the follow-up that binds the R139 release in the publication manifest, validates chain releases, and widens the closure scanner to every catalogued lane. Remaining cosmetic items (Intel 403 links, lab paths in historical prose) are left as noted.

---

# Recipe completeness audit — public reproducibility of `repro/`, `index.html`, `README.md`, `models/*.html`

Repo: `/home/steve/llm-optimizations` at `a16cb3880` (main, 2026-09-03). Read-only; no tracked file touched.
Raw tool output: `recipe-completeness-audit-raw.txt` (same directory). Checker scripts: `linkcheck.py`, `guidecheck.py` (same directory).

## Executive summary

Guides: 30 directories under `repro/`; 29 are in `repro/guide-catalog.json`, 1 is not (`rapid-model-snapshots-b70`, a single JSON, no README).

| classification | count | ids |
| --- | ---: | --- |
| candidate-portable-repro | 12 | gemma4-125tps, laguna-102tps, minimax-110tps, minimax-89tps, muse-glimmer, qwen36-autoround-int4, qwen38-fp8-tp2, qwen38-q8-tp1, qwen38-q8-q4mtp-mtp2-tp1, qwen38-q4km-tp1, qwen38-q4km-mtp2-tp1, qwen38-q4km-q4mtp-mtp2-tp2 |
| lab-replay | 8 | deepseek-v4-k160, gemma4-26b-a4b-q8-b70, laguna-125tps, qwen36-determinism, qwen36-q8-tp2, qwen38-q4km-tp2, qwen38-q8-tp2, qwen38-q8-tp2-c2 |
| research-status | 7 | qwen38-autoround-int4, qwen38-flash-next, lfm25, ornith-9b, ornith-35b, nemotron-35, qwen38-256k-vision |
| record-capsule | 1 | minimax-94tps-structured |
| archived | 1 | gemma4-95tps |
| not in catalog | 1 | rapid-model-snapshots-b70 |

What was verified clean (no findings):
- 545 relative markdown links in all `repro/**/*.md`, `README.md`, `docs/model-recipes.md` resolve to git-tracked files; 1,062 relative `href`/`src` in `index.html`, `guides.html`, `learn.html`, `models/*.html` resolve (the only unresolved ones are JS template literals inside `guides.html` `<script>`).
- 301 distinct `github.com/steveseguin/b70-optimization-lab/{blob,tree,raw,releases}` links resolve (paths against `git ls-files`, commit refs against the object store, release assets against `gh release view --json assets` for `qwen38-fp8-tp2-r55c-20260901`, `qwen38-fp8-tp2-r139-20260902`, `qwen38-fp8-kernel-1e90-20260825`, `qwen38-flash-next-runtime-2f829747-20260827`).
- 44 distinct external URLs: 41 return 200 (all Hugging Face model/revision/resolve URLs return 200; none gated); 3 Intel pages return 403 to automated requests (see Cross-cutting).
- `python3 tools/public-closure-scanner.py`: exit 0, 0/17 packages with blocking gaps; 6 `host_path_overridable_default` notes (identical to `audits/public-closure/2026-09-02-scan-after-four-b70-fix.md`).
- `python3 tools/validate-recipe-publication.py`: PASS (manifests=1, remote=False). All 15 assets named in `repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/publication-manifest.json` exist on release `qwen38-fp8-tp2-r55c-20260901` with matching byte sizes; manifest `source_commit` `8495574257dd…` is in history.
- Every `neural-download/vllm-openai-xpu:*` image tag referenced by the FP8 guide/package has a tracked builder; the R156 → R139 → R62 → R55C → R31 → R15 → R13 → `vllm/vllm-openai-xpu@sha256:f01e24f6…` chain closes (details below).
- Every catalog `dependency_links` entry and every `guide`/`package` path resolves. No git-LFS pointers; no `.gitattributes`.
- Live site: `neural.download/{docs/model-recipes.md, repro/<id>/README.md, repro/<id>/, packages/catalog.json, repro/guide-catalog.json, llms.txt, packages/<id>/README.md, models/<id>.html}` all return 200.

Gap counts (findings not already declared in the guide's own `missing` list or classification banner):

| class | count |
| --- | ---: |
| blocks-reproduction | 2 (#L1 laguna-102 venv/kernel hash gate; #C1 `validate-repro-guides.py` fails at HEAD, which blocks the publication gate rather than a build) |
| degrades | 9 |
| cosmetic | 17 |

Ordering below: newest first by last commit touching the directory (`git log -1 --format=%cs -- repro/<id>/`); dated ids noted.

---

## qwen38-27b-fp8-vllm-tp2-asrock-b70 — candidate-portable-repro (last commit 2026-09-03; package `qwen38-27b-fp8-tp2-b70`, manifest `published`)

Catalog `missing`: tested Intel driver and Docker host guide; clean-host replay; beginner recovery flow; two fresh-server clean-boot repeats of the natural-prompt 2K-32K matrix.

| file:line | finding | class | suggested fix |
| --- | --- | --- | --- |
| `repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/publication-manifest.json` (`chains.r139`, `chains.r156`) | R139 chain has `repository`, `image`, `source_repositories`, `validation` but **no `release` block**; only `release.tag=qwen38-fp8-tp2-r55c-20260901` is hash-bound. Yet `build-fixed-k-w8a16-r139-published-image.sh:13` downloads by default from release `qwen38-fp8-tp2-r139-20260902` (14 assets: `_xpu_C.abi3.so`, two oneDNN patches, `r139-clean-clone-source-rebuild.log`, `SECTION-SHA256SUMS`, …), and `README.md:125` / `models/qwen38-27b-fp8-vllm-tp2-asrock-b70.html` headline R156 on that release. `docs/recipe-publication-standard.md` requires the manifest to bind "the name, byte size, SHA-256 … of every release asset" and CI `--check-remote` only re-verifies what the manifest lists. | degrades | Add a `release` block (tag, URL, per-asset name/size/sha256, `remote_verified_at`) under `chains.r139` (or a second top-level release entry) so the daily `recipe-publication.yml` job verifies the R139 assets too. |
| `build-draft-int4-r62-image.sh:8`, `Dockerfile.draft-int4-r62:1`, `build-compiled-allreduce-custom-op-r60-image.sh:8` | Default base tag `neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-serial-fa-split-gdn-r50-reprocheck-r55c` is produced by **no** builder's default: `build-pinned-mtp1-stack.sh` and `build-pinned-mtp1-published-r55c-stack.sh` default `FINAL_IMAGE` to `…:qwen38-fp8-mtp1-r55c-public-binaries`. README documents the override only for the compiler route (`README.md:466`, `README.md:1166` set `FINAL_IMAGE=…reprocheck-r55c` before `build-pinned-mtp1-stack.sh`); the no-compiler route section (`README.md:403-408`) does not, so a reader who takes the published-binary route then `build-draft-int4-r62-image.sh` fails on `docker image inspect` of a tag that does not exist. | degrades | In the R62 section add the same `FINAL_IMAGE=…reprocheck-r55c` line for `build-pinned-mtp1-published-r55c-stack.sh`, or change the R62 builder's `BASE_IMAGE` default to `…r55c-public-binaries`. |
| `build-draft-int4-r62-image.sh:9`, `build-fixed-k-w8a16-r139-image.sh`, `build-fixed-k-w8a16-r139-published-image.sh`, `build-gdn-split-mixed-r156-image.sh:8` | `EXPECTED_BASE_IMAGE_ID` defaults to the lab host's Docker image ID (`sha256:41aec5da…`, `sha256:901ae9e0…`); an independently built base always mismatches. README does tell the reader to pass their own ID (`README.md:263-267`, `1171-1176`), but the failure text is `ERROR: R139 base image mismatch` / `draft INT4 patch identity mismatch` and does not name the variable. | cosmetic | Print `set EXPECTED_BASE_IMAGE_ID=$(docker image inspect … --format '{{.Id}}')` in the error message. |
| `README.md:271`, `README.md:381-382` | Mentions of `sycl-tla cd763790ad` and patch digests `40ca8c3f…`/`08a3de4f…` by short hash only; the referenced patch files are tracked (`experiments/qwen38-27b-b70/patches/*.patch`, verified) so this is prose, not a missing file. | cosmetic | none required |
| `run-server.sh:120`, `run-w8a16-*-server.sh` (`/root/.cache/vllm`), `build-*-image.sh` (`/opt/venv/...`) | Container-internal paths flagged by the host-path grep; they are inside the image, not host paths. | cosmetic (false positive) | none |
| `README.md:979` | `https://www.intel.com/…/oneapi-toolkit/2026.html` returns 403 to automated HEAD/GET (bot protection); not verified reachable. | cosmetic | none, or link the dgpu-docs page instead |

## minimax-m27-b70-89tps-20260520 — candidate-portable-repro (commit 2026-09-02; package `minimax-m27-int4-autoround-b70`)

Catalog `missing`: current clean-host replay; beginner recovery and platform compatibility boundary.

| file:line | finding | class | suggested fix |
| --- | --- | --- | --- |
| `scripts/01-download-model.sh:4-6` | `MODEL_ID=Lasimeri/MiniMax-M2.7-int4-AutoRound`, `MODEL_REVISION=1afac074…`, `MODEL_DIR` defaults to `/mnt/fast-ai/llm-models/…` — all overridable; download path is public. | clean | — |
| `README.md:81` | Example `bash scripts/06-summarize-result.sh /mnt/fast-ai/bench-results/minimax-m27-b70-89tps` uses a lab path as a positional example argument. | cosmetic | Use `/path/to/bench-results` in the example. |
| `scripts/run-vllm-minimax-quality-check.py:27,68,787` (referenced) | `~/.venvs/vllm-xpu`, `/mnt/fast-ai/llm-models/…`, `/mnt/fast-ai/llm-cache/hf` as overridable defaults (scanner: `host_path_overridable_default`). | cosmetic | none required |
| `manifests/current-system-20260520.md:154` | `https://apt.repos.intel.com/oneapi` returns 403 to HEAD (bot protection). | cosmetic | none |
| `README.md:1-14` | No classification banner; catalog says `candidate-portable-repro`. | cosmetic | Add the one-line certification banner used by the Qwen3.8 guides. |

## laguna-s-2.1-int4-b70-125tps-20260731 — lab-replay (commit 2026-09-02; package `laguna-s-2.1-int4-b70-125tps`)

Catalog `missing`: portable runtime rebuild; platform installation; model acquisition; non-originating-host replay.

| file:line | finding | class | suggested fix |
| --- | --- | --- | --- |
| `packages/laguna-s-2.1-int4-b70-125tps/package.json` | `python3 tools/validate-repro-guides.py` **fails at HEAD**: `entrypoint dependency must be declared in dependencies: repro/laguna-s-2.1-int4-b70-125tps-20260731/teacher-q1-canonical-bench.json` (file was added 2026-09-02 by the four-B70 fix, `audits/public-closure/HANDOFF-four-b70-host.md`). This is gate 9 of the publication standard and the `guides.yml` CI check. | blocks (publication gate) | Add `repro/laguna-s-2.1-int4-b70-125tps-20260731/teacher-q1-canonical-bench.json` to `dependencies` in `package.json`, regenerate `packages/catalog.json` with the tool. |
| `run-record-gate.sh:5-9` | Now `REPRO_*`-overridable lab defaults (`/home/steve/llm-optimizations`, `/home/steve/src/laguna-vllm-shared-elementwise-m12-20260731`, `/mnt/fast-ai/...`); scanner reports clean. | cosmetic | none |
| `README.md:38-39` | Bundles `patches/laguna-s-2.1-xpu-b70/vllm-laguna-shared-elementwise-m12-1a7f61fef-20260731.bundle` and `…-99886d783-20260731.bundle` are tracked (verified). | clean | — |
| `README.md:26` | `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/` in a code fence as the run directory; guide is a declared originating-host replay. | cosmetic | none |

## laguna-s-2.1-int4-b70-102tps-20260726 — candidate-portable-repro (commit 2026-09-02)

Catalog `missing`: tested host-platform installation; independent clean-host replay.

| file:line | finding | class | suggested fix |
| --- | --- | --- | --- |
| `run.sh:19-20,118-130` | `run.sh` hash-gates the **lab virtualenv and kernel binaries**: `$venv_root/bin/python` (`202c17d1…`), `$venv_root/bin/vllm`, `$venv_root/lib/libccl.so.2.0`, `libsycl.so.8.0.0`, `libmhc_kernels_xe_2.so`, and `xpumem_allocator.abi3.so` (`8981f5e3…`). Defaults `/home/steve/.venvs/deepseek-v4-xpu` and `/home/steve/src/deepseek-v4-xpu-kernels-qnorm-routeportfolio/...` are overridable (`REPRO_VENV_ROOT`, `REPRO_XPUMEM_MODULE`, documented at `README.md:117-118`) but there is no public builder that reproduces those hashes (`HANDOFF-four-b70-host.md` "pinned venv binaries … have no public builder"). `README.md:125-126` says a rebuild "is a new environment", but `run.sh` has no rebuilt-environment mode: a third party's `run.sh` stops at `check_hash`. Catalog `missing` does not list this. | blocks-reproduction (of `run.sh` as written) | Either add a documented `REPRO_RUNTIME_LOCK` override path that accepts a freshly generated lock (the var exists in `run.sh`; document how to generate it), or add "no public builder for the pinned venv/oneCCL/xpumem binaries" to the catalog `missing` list and README banner. |
| `README.md:69`, `README.md:81`, `README.md:153`, `BUILD.md:28`, `BUILD.md:54` | Lab destinations (`/mnt/fast-ai/laguna-repro-sources`, `/mnt/fast-ai/llm-models/laguna-s-2.1`, `/mnt/fast-ai/llm-optimization-artifacts/...`) used as positional example arguments in code fences. | cosmetic | Use `/path/to/...` placeholders. |
| `README.md:100-107` | "exact lab replay expects" list includes venv `/home/steve/.venvs/deepseek-v4-xpu`, NVMe `/dev/nvme0n1p2` ext4, cluster IP `10.0.0.65`; all overridable (`REPRO_VENV_ROOT`, `REPRO_NVME_DEVICE`, `REPRO_NVME_FSTYPE`, `REPRO_CLUSTER_IP` — `run.sh:21`) and documented. | cosmetic | none |
| `manifests/model-directory-verification.sha256` | 86/118 entries are HF download-cache metadata (per HANDOFF); `restore-models.sh --verify` on a fresh download will not match them. Declared in `README.md:87-95`. | degrades (declared) | Ship a release-files-only manifest as the default verify target (`manifests/model-release-files.sha256` already exists — `restore-models.sh:6`). |
| `BUILD.md:93`, `BUILD.md:98` | `source /opt/intel/oneapi/compiler/2025.3/env/vars.sh` and `python setup.py` inside the restored vLLM tree — platform/upstream files, version named. | clean | — |
| `README.md:1-14` | No classification banner. | cosmetic | Add banner. |

## gemma4-26b-a4b-q8-b70 — lab-replay (commit 2026-09-02)

Catalog `missing`: platform installation; self-contained model acquisition and direct verification; self-contained source restore/build.

| file:line | finding | class | suggested fix |
| --- | --- | --- | --- |
| `run-vdr2-selecteddown-record.sh:48` | Q4_0 MTP draft path now `MTP_DRAFT_MODEL`-overridable (per HANDOFF); scanner clean. | clean | — |
| `scripts/run-gemma4-26b-llamacpp-replica.sh:7-8,27` (referenced) | `MODEL`, `OUT_DIR` default to `/mnt/fast-ai/...`; `LLAMA_SERVER` defaults to `/home/steve/src/llama.cpp-gemma-record-repro-c926/.../llama-server`. Overridable, but the script never tests `-x "$LLAMA_SERVER"` — on a fresh host it fails at exec with a bare "No such file" rather than naming the variable. | degrades | Add `[[ -x "$LLAMA_SERVER" ]] || { echo "set LLAMA_SERVER=…"; exit 2; }`. |
| `README.md:1-14` | No classification banner (catalog: lab-replay). | cosmetic | Add banner. |

## qwen38-flash-next-fp8-tp4-mtp3-b70 — research-status (commit 2026-08-31)

`README.md:3` states: "Status: `research-status` / runtime hosted; not a runnable guide." Catalog `missing`: exact installable dependency lock; portable four-B70 platform/topology preflight; artifact-only origin-host replay; runnable launch/qualification/controlled-stop path.

| file:line | finding | class | suggested fix |
| --- | --- | --- | --- |
| `dependency-contract.json` (4 host paths), `experiments/qwen38-flash-next-fp8-b70/tools/launch-tp4-ep4-eager-mtp4-512.sh:23` (`KERNEL_STAGE=/mnt/usb-models/qwen38-build/...`, hard-coded) | Lab-only paths in a lane that declares itself not runnable; release `qwen38-flash-next-runtime-2f829747-20260827` exists (pre-release). | cosmetic (declared) | none until promotion |

## qwen38-27b-autoround-int4-b70 — research-status (commit 2026-08-31)

`README.md:7-13` status correction says no promoted record. Catalog `missing`: promoted deterministic lane; published AOT binaries or portable rebuild; portable compile-cache identity; clean-host replay.

| file:line | finding | class | suggested fix |
| --- | --- | --- | --- |
| `experiments/qwen38-27b-b70/scripts/run-20260822-qwen38-tp1-nightly-docker-bench.sh:26-28,68` (referenced from README) | **Hard-coded, not overridable**: `model=/mnt/usb-models/llm-models/qwen3.8-27b-int4-autoround-devan`, `venv=/home/steve/.venvs/vllm-xpu`, `cache_root=/mnt/usb-models/...`, `-v /mnt/usb-models:/mnt/usb-models`. | degrades (lane declared research) | Convert to `${VAR:-default}` with fail-closed messages before any promotion. |
| `README.md:107,111,286-287`, `REFERENCE-HOST-HANDOFF.md:4,15`, `ONECCL-BUILD-20260818.md:25-27`, `RUNTIME-BUILD-20260818.md:26-27` | `/mnt/usb-models/...`, `/home/steve/src/...`, hostname `steve-b70s` in code fences/prose. | cosmetic (declared) | none until promotion |
| `README.md:1-14` | No classification banner (status correction is present). | cosmetic | Add `research-status` banner. |

## qwen38-27b-q4km-tp2-asrock-b70 — lab-replay (commit 2026-08-30; package)

Catalog `missing`: platform installation; model download/verification; clean-host replay.

| file:line | finding | class | suggested fix |
| --- | --- | --- | --- |
| all | Links, scripts (`run-server.sh`, `bench.sh`, `runtime-common.sh`), HF revision URL resolve; scanner clean. `QWEN38_*` vars are set in `runtime-common.sh`. | clean | — |
| `README.md:1-14` | No classification banner (catalog: lab-replay). | cosmetic | Add banner. |

## qwen38-27b-q4km-q4mtp-mtp2-tp2-b70 — candidate-portable-repro (commit 2026-08-30; package)

Catalog `missing`: measured 32K profile; output-qualified concurrency profile; tested clean-host Intel/oneAPI install; clean-host source build and endpoint replay; beginner recovery replay. `README.md:3` banner: "Lab-validated candidate package … Clean-host Intel/oneAPI installation and source-build replay remain pending."

| file:line | finding | class | suggested fix |
| --- | --- | --- | --- |
| all | clean | clean | — |
| `sitemap.xml` | `models/qwen38-27b-q4km-q4mtp-mtp2-tp2-b70.html` is tracked and live (200) but absent from the sitemap. | cosmetic | Add `<loc>`. |

## qwen38-27b-q8-tp2-asrock-b70 — lab-replay (commit 2026-08-27; package)

| file:line | finding | class | suggested fix |
| --- | --- | --- | --- |
| all | clean (links, `run-server.sh`, `bench.sh`, HF URL). `README.md:148` `707ea1b8...` SYCL library hash is a provenance aid, stated as such. | clean | — |
| `README.md:1-14` | No classification banner. | cosmetic | Add banner. |

## qwen38-27b-q8-tp1-b70 — candidate-portable-repro (commit 2026-08-27; package)

Banner present (`README.md:3`). Catalog `missing`: clean-host Intel/oneAPI install; clean-host build and replay; beginner recovery; realistic-prompt sweep; concurrency curve.

| file:line | finding | class | suggested fix |
| --- | --- | --- | --- |
| all | clean | clean | — |

## qwen38-27b-q8-q4mtp-mtp2-tp1-b70 — candidate-portable-repro (commit 2026-08-27; package)

Banner present. | all | clean | clean | — |

## qwen38-27b-q4km-tp1-b70 — candidate-portable-repro (commit 2026-08-27; package)

Banner present.

| file:line | finding | class | suggested fix |
| --- | --- | --- | --- |
| `CLEAN-HOST.md:20` | `https://www.intel.com/…/install-oneapi-toolkit-with-apt.html` returns 403 to automated requests; not verified. | cosmetic | none |
| `README.md:188` | `source /opt/intel/oneapi/setvars.sh` — allowed platform path; oneAPI version is named in `CLEAN-HOST.md`. | clean | — |

## qwen38-27b-q4km-mtp2-tp1-b70 — candidate-portable-repro (commit 2026-08-27; package)

Banner present (`README.md:3`). | all | clean | clean | `sitemap.xml` lacks `models/qwen38-27b-q4km-mtp2-tp1-b70.html` (cosmetic). |

## ornith-15-9b-q8-b70 — research-status (commit 2026-08-27; package)

`README.md:3-7`: "strict headline withheld". Catalog `missing`: tested clean-host platform installation; additional operating points.

| file:line | finding | class | suggested fix |
| --- | --- | --- | --- |
| `model-manifest.json` | `repository: ornith-ai/Ornith-1.5-9B-GGUF`, `revision: 85bf2b98…`, 1 file with hash; `store_dir: /mnt/usb-models/...` is data, and the package README's verifier takes a path argument. | clean | — |
| `README.md:55` | `source /opt/intel/oneapi/setvars.sh` (platform path). | clean | — |

## ornith-15-35b-a3b-q4km-b70 — research-status (commit 2026-08-27; package)

| file:line | finding | class | suggested fix |
| --- | --- | --- | --- |
| `README.md:61-62`, `185-186` | `git apply "$PATCH"` / `"$MULTIROW_PATCH"` — variables are assigned from tracked `patches/` files immediately above (verified by link resolution). | clean | — |
| `README.md:97` | `/path/to/b70-optimization-lab/scripts/verify-neural-download-model.py` placeholder; target script tracked. | clean | — |

## nemotron-35-lightning-30b-a3b-b70 — research-status (commit 2026-08-27; package)

`README.md:1` title says "DRAFT: benchmarks pending"; `README.md:3-8` says raw JSON not closed. | `model-manifest.json` repository `unsloth/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-GGUF` @ `f2d3fe36…` | clean | — |

## lfm25-26b-q8-b70 — research-status (commit 2026-08-27; package)

| all | clean (`model-manifest.json`: `LiquidAI/LFM2.5-2.6B-GGUF` @ `f4a289c8…`; `README.md:43` `setvars.sh` platform path) | clean | — |

## deepseek-v4-flash-k160-b70-80tps-20260718 — lab-replay (commit 2026-08-26)

Catalog `missing`: clean-host platform installation; self-contained model and DSpark acquisition; self-contained runtime build path.

| file:line | finding | class | suggested fix |
| --- | --- | --- | --- |
| `README.md:33-35,50-94` | Runtime identities are given by commit and by tracked bundles/patches: `patches/deepseek-v4-flash-reap-xpu-b70/*.bundle` (3.5 KB - 152 KB), `*.patch`, `*.provenance.json` — all tracked and non-empty (verified). Release tags on `steveseguin/vllm` return 200. | clean | — |
| `README.md:48,51,57-58` | Code fences set `repo=/home/steve/llm-optimizations` and `src=/home/steve/src/vllm` (14 lab paths in fences). Lab-replay by catalog, but the README itself never says so. | cosmetic | Use `/path/to/...` and add the lab-replay banner. |

## qwen38-27b-256k-vision-mtp-b70 — research-status (commit 2026-08-23; package)

`README.md:1` "DRAFT: fit-off pending". | `model-manifest.json`: `unsloth/Qwen3.8-27B-GGUF` @ `4ca72078…`, 4 files | clean | — |

## qwen36-27b-autoround-int4-b70 — candidate-portable-repro (commit 2026-08-23)

Catalog `missing`: tested platform installer; clean-host replay; simplified canonical positive patch index.

| file:line | finding | class | suggested fix |
| --- | --- | --- | --- |
| `README.md:86,135-136,147` | "detached e7213ba8… + exact dirty patch" — patch packet is `patches/qwen36-27b-autoround-int4-b70/record-20260711/` (tracked, linked). | clean | — |
| `HISTORICAL_RECIPES.md:53` → `experiments/qwen36-27b-autoround-int4-b70/scripts/download-model.sh:17` | Historical script hard-codes `repo_dir = Path("/home/steve/llm-optimizations")` (not overridable). The **current** packet's `repro/qwen36-27b-autoround-int4-b70/scripts/download-model.sh` has no host paths (verified), so only the historical route is affected. | cosmetic (historical) | Mark the HISTORICAL route as lab-only or fix the path. |
| `HISTORICAL_RECIPES.md` (13 fenced lab paths), `experiments/qwen36-27b-autoround-int4-b70/scripts/serve-vllm.sh:18-20` (reads `/home/steve/.config/huggingface/token` only if it exists) | historical / guarded. | cosmetic | none |
| `README.md:1-14` | No classification banner. | cosmetic | Add banner. |

## gemma4-26b-a4b-q8-b70-125tps-20260701 — candidate-portable-repro (commit 2026-08-22; package `gemma4-26b-a4b-q8-b70`)

`README.md:4-8` reconstruction-status note present. Catalog `missing`: tested clean-host platform installation; historical local Q4_0 draft and server binary hashes; clean one-B70 rebuild and endpoint replay.

| file:line | finding | class | suggested fix |
| --- | --- | --- | --- |
| `restore-and-build.sh:6-37` | Fails closed (`SOURCE_DIR` required with message), clones `ggml-org/llama.cpp` tag `b9769`, checks base commit `c926ad09…`, decodes tracked `patches/gemma4-26b-a4b-q8-b70/llama-cpp-c926ad098-gemma4-q8-record-source-20260701.diff.gz.b64` and checks its SHA-256; compiler default `/opt/intel/oneapi/compiler/2026.0` (version named in README:108). | clean | — |
| `README.md:80-81` | Prose names the record binary at `/home/steve/src/llama.cpp-gemma-record-repro-c926/.../llama-server` — historical identity only. | cosmetic | none |
| `scripts/run-gemma4-26b-first-baseline.sh:10`, `scripts/run-gemma4-26b-llamacpp-replica.sh:8` | Same `/home/steve/src/...` `LLAMA_SERVER` default as noted above; README:169,184 show `LLAMA_SERVER=/path/to/build/bin/llama-server`. | degrades (no `-x` check) | Add existence check. |
| HF links | `unsloth/gemma-4-26B-A4B-it-GGUF` resolve URLs @ `3bb10d59…` return 200. | clean | — |

## qwen36-27b-autoround-int4-b70-determinism-20260818 — lab-replay (commit 2026-08-18)

Catalog `missing`: inherits historical dependencies; clean-host replay.

| file:line | finding | class | suggested fix |
| --- | --- | --- | --- |
| `README.md:147` | Spec arms load `experiments/qwen27_graphsafe_flash_attention/staged-package` — that directory is **git-ignored** (`experiments/qwen27_graphsafe_flash_attention/.gitignore:2`, 3.1 GB AOT `.so` files). `README.md:160-172` documents this and points to the tracked `build.sh` + three patches; bit-identical rebuild is stated as impossible. | degrades (declared) | none beyond the existing note; consider listing it in catalog `missing`. |
| `README.md:303` | `data/quality.json` is a run output path, not an input. | cosmetic (false positive) | none |
| `README.md:58-59,192,211` | `~/.venvs/vllm-xpu`, `/mnt/usb-models/...` in fences (22 prose host-path hits, most in the identity tables). | cosmetic (lab-replay) | none |

## qwen38-27b-q8-tp2-c2-asrock-b70 — lab-replay (commit 2026-08-16)

| all | clean; inherits the Q8 TP2 replay. `README.md:1-14` has no banner. | cosmetic | Add banner. |

## qwen36-27b-q8-tp2-asrock-b70 — lab-replay (commit 2026-08-15)

Catalog `missing`: OMIX driver installation and verification; model download helper; clean-host replay.

| file:line | finding | class | suggested fix |
| --- | --- | --- | --- |
| `README.md:55-58` | Sources `/opt/intel/oneapi/{tbb/2023.1,compiler/2026.1,mkl/2026.1,umf/1.0}/env/vars.sh` — allowed platform paths with versions in the line. | clean | — |
| `README.md:1-14` | No banner; `ggml-org/Qwen3.6-27B-GGUF` link 200 but no revision pinned in the URL (catalog already lists "model download helper" missing). | cosmetic | Pin the HF revision. |

## muse-glimmer-30b-q8-woq-b70-100tps-20260813 — candidate-portable-repro (commit 2026-08-14; package)

Catalog `missing`: tested platform installer; original download-time complete target identity; independent clean-host replay.

| file:line | finding | class | suggested fix |
| --- | --- | --- | --- |
| `README.md:67` | `python3 convert_hf_to_gguf.py` is llama.cpp's upstream script (run inside the restored tree). | clean | — |
| HF links | `unsloth/Muse-Glimmer-30B-GGUF/resolve/faa5b025…/Muse-Glimmer-30B-UD-Q8_K_XL.gguf`, `meta-models/Muse-Glimmer-30B[-assistant]` return 200. `patches/2026-08-13-muse-q8-width16-mmq-negative.patch` tracked. | clean | — |
| `manifests/expected-result.json` (5 lab paths) | evidence data, not inputs. | cosmetic | none |
| `README.md:1-14` | No banner. | cosmetic | Add banner. |

## rapid-model-snapshots-b70 — NOT IN CATALOG (commit 2026-07-04)

| file:line | finding | class | suggested fix |
| --- | --- | --- | --- |
| `repro/rapid-model-snapshots-b70/` | Contains only `realistic-suite-v1.json`; no README, no `guide-catalog.json` entry, yet `README.md:130` links it as "Rapid one-B70 model snapshots". `repro/README.md:3-5` says every `repro/` directory is classified by the catalog. | degrades | Add a catalog entry (`record-capsule` or `archived`) with a short README, or move the suite file under `data/rapid-model-snapshots-b70/`. |

## gemma4-26b-a4b-q8-b70-95tps-20260624 — archived (commit 2026-07-02)

`README.md:3` "superseded historical reproduction recipe". | `README.md:107-108,155-156` lab paths in fences; `scripts/0{0,1,2}-*.sh` take `GEMMA_*`/`LLAMA_CPP_*` from an env file. | cosmetic (archived) | none |

## minimax-m27-b70-94tps-structured-20260522 — record-capsule (commit 2026-07-01)

| file:line | finding | class | suggested fix |
| --- | --- | --- | --- |
| `README.md:27,32,35`; `scripts/run-minimax-structured-skeleton-quality.py:85-97,197` (referenced) | Fences use `/home/steve/llm-optimizations`, `/home/steve/.venvs/vllm-xpu/bin/python`; the script hard-codes `/home/steve/src/llm-scaler/vllm/custom-esimd-kernels-vllm/python` and `/home/steve/.venvs/vllm-xpu/lib/...` (`LD_LIBRARY_PATH` prepend; only `HF_HOME` and `MINIMAX_M27_MODEL` are overridable). | degrades (declared constrained-task record) | Apply the same `VENV`/`LLM_SCALER_KERNELS` overrides used in `scripts/run-vllm-minimax-quality-check.py`. |
| `README.md:1-14` | No banner. | cosmetic | Add `record-capsule` banner. |

## minimax-m27-b70-110tps-ubuntu24-20260523 — candidate-portable-repro (commit 2026-05-25)

Catalog `missing`: immutable driver package lock; complete patch manifest with checksums; fresh clean-host replay.

| file:line | finding | class | suggested fix |
| --- | --- | --- | --- |
| `docs/model-recipes.md:60-78` | `cd repro/minimax-m27-b70-110tps-ubuntu24-20260523` then `scripts/00…07*.sh` — all eight scripts tracked (verified). | clean | — |
| `scripts/00-install-system-deps.sh:30-39` | `add-apt-repository ppa:kobuk-team/intel-graphics` then unpinned `apt-get install intel-opencl-icd libze-intel-gpu1 …` (no `=version`). Declared in catalog `missing`. | degrades (declared) | Pin package versions and record the PPA signing-key fingerprint per `docs/reproduction-guide-certification.md`. |
| `configs/runtime-env.sh:3-11` | `FAST_AI_ROOT=/mnt/fast-ai` default drives `MODEL`, `SRC_ROOT`, `VLLM_SRC`, `LLM_SCALER_ROOT`, `BENCH_ROOT`; `VENV=$HOME/.venvs/vllm-xpu`. All `${VAR:-}`-overridable; no fail-closed message when the root is absent. | cosmetic | Add an existence check with the variable name. |
| `README.md:300,317` | Model id shown as `/mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround` in a text block. | cosmetic | Show `$MODEL`. |
| `README.md:1-14` | No banner. | cosmetic | Add banner. |

---

## Cross-cutting

| file:line | finding | class | suggested fix |
| --- | --- | --- | --- |
| `tools/validate-repro-guides.py` at HEAD `a16cb3880` | Exits 1: `packages/laguna-s-2.1-int4-b70-125tps/package.json: entrypoint dependency must be declared in dependencies: repro/laguna-s-2.1-int4-b70-125tps-20260731/teacher-q1-canonical-bench.json`. `repro/README.md:12-14` and the publication standard (gate 9) require this validator to pass; CI `guides.yml` will be red. | blocks (publication gate) | Declare the dependency in the package manifest; regenerate the catalog. |
| `repro/rapid-model-snapshots-b70/` vs `repro/guide-catalog.json` | One `repro/` directory outside the catalog (see section above). | degrades | Add catalog entry. |
| `sitemap.xml` | 12 tracked pages absent: `models/{qwen38-27b-q4km-mtp2-tp1-b70,qwen38-27b-q4km-q4mtp-mtp2-tp2-b70,deepseek-coder-v2,deepseek-v4,glm-4-7,mistral-small-3-2,nemotron-cascade-2,phi-4,qwen-14b,qwen-30b-a3b,qwen-35b}.html` (`models/index.html` is covered by `models/`). All 57 listed `<loc>` URLs resolve to tracked files; sampled live URLs return 200. | cosmetic | Regenerate the sitemap. |
| `llms.txt` | 87 links; all resolve (tracked paths / 200). | clean | — |
| `index.html`, `guides.html`, `models/*.html` | `guides.html:343` builds cards from `packages/catalog.json`; for all 17 packages `models/<id>.html`, `guide`, `manifest`, and `commands.*` paths are tracked. "Install guide" appears only in the negated sense (`index.html:659` "reserved for a complete clean-host …"; `models/*.html:124` "Still missing before this becomes an install guide"), consistent with `docs/reproduction-guide-certification.md`. `data-copy` / `data-copy-markdown` fetch targets (10) all tracked. | clean | — |
| `README.md:39,126,155` | `prompts/workflows` and `repro/status` flagged by the bare-path grep are prose ("prompts/workflows", "[repro/status](…)" link text), not paths; the links themselves resolve. | cosmetic (false positive) | none |
| External 403s | `https://apt.repos.intel.com/oneapi` (`repro/minimax-m27-b70-89tps-20260520/manifests/current-system-20260520.md:154`), `https://www.intel.com/…/oneapi-toolkit/2026.html` (`repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/README.md:979`), `https://www.intel.com/…/install-oneapi-toolkit-with-apt.html` (`repro/qwen38-27b-q4km-tp1-b70/CLEAN-HOST.md:20`) return 403 to automated HEAD and ranged GET with a browser UA; reachability from a browser was not verified. | cosmetic | Prefer `dgpu-docs.intel.com` (200) where possible. |
| Classification banners | 18 of 29 catalogued READMEs carry no classification statement in their first 14 lines (list in raw file, "README heads"); only the five Qwen3.8 llama.cpp guides, the FP8 guide, and Flash-Next carry an explicit banner. The certification doc requires the table only for starter guides, so this is presentation, but `models/*.html` "Read guide" links land readers on READMEs that do not say lab-replay/research-status. | cosmetic | Add a one-line `> **Certification: <class>**` banner to each. |
| Scanner blind spot | `tools/public-closure-scanner.py` crawls only the 17 catalogued packages, so `repro/{deepseek-v4-flash-k160-…, gemma4-26b-a4b-q8-b70-95tps-…, laguna-s-2.1-int4-b70-102tps-…, minimax-m27-b70-110tps-…, minimax-m27-b70-94tps-…, qwen36-27b-autoround-int4-b70(-determinism-…), qwen36-27b-q8-tp2-asrock-b70, qwen38-27b-autoround-int4-b70, qwen38-27b-q8-tp2-c2-asrock-b70, qwen38-flash-next-…, rapid-model-snapshots-b70}` are never scanned by CI for hard-coded host paths; the hard-coded findings above (`run-20260822-qwen38-tp1-nightly-docker-bench.sh`, `run-minimax-structured-skeleton-quality.py`, `launch-tp4-ep4-eager-mtp4-512.sh`, historical `download-model.sh`) are all in that set. | degrades | Extend the scanner to every `repro/*/` directory (seeded from `guide-catalog.json`), reporting non-candidate lanes as informational. |
