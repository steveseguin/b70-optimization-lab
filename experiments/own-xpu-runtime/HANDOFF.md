# Own-engine SC117 lane: handoff guide (2026-10-31)

For the next agent taking over the own-engine SC117 work on the four-card host (`steve-b70s`). Read this, then the
files in "Read first". Everything here is linked to evidence in the repo; where a number is a projection it says so.

## Read first

1. [`AGENTS.md`](../../AGENTS.md): owner rules (no power/memory settings, no reboots or driver resets, no restart
   loops, lossless only, main branch only, explicit staging, never print secrets).
2. [`CURRENT.md`](../../CURRENT.md): live state and the dated owner decisions still open.
3. [`IDEAS.md`](IDEAS.md), section "Toward 200 tok/s" and its subsection "Where it stands after two days": the plan,
   everything measured and closed, and why 200 tok/s is not reachable with the known levers.
4. [`gsq-rco-iq3s/service-speed/DO-NOT-REPEAT.md`](gsq-rco-iq3s/service-speed/DO-NOT-REPEAT.md): every closed lever.
   Check it before opening an experiment.
5. The result folders under [`research/`](research/) and [`research/tp/`](research/tp/) dated 2026-10-28 to
   2026-10-31. Each has a `RESULT.md` with plain-words summary first.

## State at handoff

Model: SC117 Qwen3.8 Flash-Next GSQ-RCO IQ3_S (125B total, ~6B active), our own SYCL/C++ engine, F32 activations,
F32 recurrent state and KV, greedy, official FP8 MTP draft (76.1% of guesses accepted). Every number below has
outputs bit-identical to build B19 (12-prompt suite) and, for the long prompt, to the 3 + 1 262K reference.

| | 2026-10-29 | Committed in `engine/src` | Lab build (patches not in `engine/src`) |
| --- | ---: | ---: | ---: |
| Four cards, decode, 12-prompt suite median | 78.3 tok/s | 87.6–87.8 tok/s ([hc-kernels](research/hc-kernels-2026-10-30/RESULT.md)) | **94.0–94.3 tok/s** ([hc-split](research/tp/hc-split-2026-10-30/RESULT.md)) |
| Two cards, decode | 66.1 tok/s | — | **72.4 tok/s** ([two-card-flags](research/two-card-flags-2026-10-31/RESULT.md)) |
| Four cards, 121,854-token prompt, first token | 353.6 s | **216.7 s** ([prefill-balance](research/tp/prefill-balance-2026-10-31/RESULT.md)) | 215.7 s with the HC split, before the last two prefill steps |
| Fresh four-card server, launch to ready | — | — | 528–554 s with AOT kernels, 670–695 s JIT ([aot-tp](research/aot-tp-2026-10-31/RESULT.md)) |

- Four-card layout: two pipeline ranks (rank 0 = layers 0–22 + MTP draft on cards 23+27; rank 1 = layers 23–47 + head
  on cards 43+47), each split exactly across its two cards ("TP"). The committed four-card flag set is
  `tptsxqckhcbgl`, defined in
  [`research/tp/prefill-balance-2026-10-31/arm_env.py`](research/tp/prefill-balance-2026-10-31/arm_env.py) (plus
  `--tp-replicate`, passed by the lab adapter). The lab decode set adds `OWNRT_DRAFT_FAST=1 OWNRT_TARGET_FAST=1`
  (fixed-cost-2) and `OWNRT_TP_HC_SPLIT=low,gate,final,prefill` (hc-split).
- Two-card layout: one card per rank, no TP. Its lab flag set is `B` in
  [`research/two-card-flags-2026-10-31/flags.py`](research/two-card-flags-2026-10-31/flags.py).
- The `sc117-lan` service (two cards, B19 build, unit in `gsq-rco-iq3s/serving/lan/`) is stopped and untouched.
  Nothing is hosted on the cards.

## Owner decisions still open (do not act on these without the owner)

1. **Apply the lab patches to `engine/src`** (raised 2026-10-30). The permission system refused an agent's copy of
   the merged files into `engine/src`; nobody routed around it. The patches:
   [`engine-fixed-cost-2.patch`](research/tp/fixed-cost-2-2026-10-30/engine-fixed-cost-2.patch) (against `979462f7c`),
   then [`engine-hc-split.patch`](research/tp/hc-split-2026-10-30/engine-hc-split.patch). They carry four-card decode
   from ~87.7 to ~94.2 tok/s and two-card from 66.1 to 72.4.
2. **Strictly rounded GPU F32 divide/sqrt** (raised 2026-10-31). The lab builds carry no offload precision flags on the
   link line, so the GPU uses the compiler's default divide/sqrt rounding (JIT and AOT alike). Adding them changes
   outputs; it may bear on the open CPU-reference disagreements. Needs its own gate.
3. **Moving `sc117-lan` to the new build** (and possibly to four cards): service change, owner's call.
4. **Upstream libsycl bug report** (shared-context kernel-cache thrash, see
   [fault-ladder RESULT](research/tp/fault-ladder-2026-10-29/RESULT.md)) and any **LocalMaxxing** submission:
   outward-facing, owner's call.

## Finish first

1. **Shared-expert split for prefill** (`OWNRT_PREFILL_SHEXP_SPLIT=1`,
   [`research/tp/prefill-shexp-split-2026-10-31/`](research/tp/prefill-shexp-split-2026-10-31/)): exact in every
   harness gate, −6.1 / −8.0 ms per chunk (rank 1 / rank 0), decode unchanged. Its fresh-server A/B/B at 131072 was
   running at handoff; see that folder's RESULT.md for the outcome. If it won, commit the engine change to
   `engine/src` (default off), publish the new long-prompt time, and make `tptsxqckhcbgls` the four-card set.
2. **If the owner approves decision 1**, merge in this order and re-gate:
   - `engine/src` HEAD already contains later changes (GDN registers, prefill balance, possibly the shared-expert
     split). Apply `engine-fixed-cost-2.patch` and `engine-hc-split.patch` with a 3-way merge onto HEAD. The known
     overlap is `round2_submit.cpp` (fixed-cost-2's `StaticState` gdnr change vs the GDN-registers change); see
     [`engine-gdn-regs-on-fc2-hcsplit.patch`](research/tp/prefill-tp-overhead-2026-10-30/engine-gdn-regs-on-fc2-hcsplit.patch)
     for the resolved form.
   - Rebuild with `engine/build.py` (JIT), check every compiled-source hash against the patched tree
     ([`verify_receipt.py`](research/tp/fixed-cost-2-2026-10-30/verify_receipt.py) shows how).
   - Gates on the merged binary: one-card rank harness both ranks (h / hmcn / m on rank 0), rank 1 exported draft rows,
     the two-request case with the exact-pattern ones checker, the four-card TP harness bitwise against one card, and
     the decode-half check against the previous binary (within 0.3%).
   - Fresh servers: four cards A/B/A/B at 65536 (decode), A/B/B at 131072 (long prompt), two cards A/B/A/B at 65536.
     Both arms on the merged binary.
   - Then build it AOT (`python3 -B engine/build.py OUT --jobs 4 --name sc117-engine --aot-target intel_gpu_bmg_g31`)
     and run the JIT-vs-AOT bitwise gate from [aot-tp](research/aot-tp-2026-10-31/RESULT.md).
3. **Durability of builds.** Many receipts pin source trees and builds in `/dev/shm` (for example
   `pto-engine-20261031-gdn`, `pbal-engine-20261031-b`, `fc2-2026-10-30`, `hcsplit-2026-10-30`,
   `aot-tp-2026-10-31`, `pss-engine-20261031`); some binaries read their rope table from that tree. `/dev/shm` is
   wiped on reboot. Copies are on the RAID under
   `/mnt/raid-models/ownrt-experiment-archives/2026-10-3x/engine-builds/`. Anything meant to last must be rebuilt from
   `engine/src` (or from the merged tree) and re-gated, not run from `/dev/shm`.

## Publication: complete recipes on neural.download and in this repo

The owner wants neural.download and this repository to carry complete, validated recipes and benchmarks for this
engine, in the style of the existing documented packages and graphs. Plan:

- **Where:** the package
  [`packages/sc117-iq3s-b70-research-draft-20261028/`](../../packages/sc117-iq3s-b70-research-draft-20261028/package.json)
  (status `candidate` today), the page [`own-runtime.html`](../../own-runtime.html) section `current-sc117`, the
  README "Current focus" table, the featured banner (generated by `tools/featured_picks.py` via
  `tools/build-model-pages.py`), `llms.txt`, and generated `models/*.html`.
- **How:** follow the repository skill [`publish-model-package`](../../.agents/skills/publish-model-package/SKILL.md)
  and [`docs/recipe-publication-standard.md`](../../docs/recipe-publication-standard.md). Pin model files, engine
  commit and build command, flags, card placement and commands; close every dependency inside the repo; validate with
  `tools/validate-repro-guides.py`, `tools/validate-recipe-publication.py` (local and remote modes),
  `tools/check-doc-links.py`, `tools/check-manifest-paths.py`, `tools/sync-public-result-summary.py --check`,
  `tools/build-family-pages.py --check`, and the `run:` lines of `.github/workflows/guides.yml`.
- **What to publish:** separate operating profiles for four cards (TP) and two cards (pipeline), each with decode
  (realistic 12-prompt suite, cold, `cached_tokens=0`, class medians and the median across classes as AGENTS.md
  defines) and prompt reading (TTFT at the measured prompt lengths), plus a context graph built only from measured
  points (64K and 131072 are measured; never interpolate or extrapolate). Match the look of the existing benchmark
  tables and context-performance graphs on other model pages.
- **Before claiming "reproducible":** a clean rebuild from the committed source must reproduce the binary's
  compiled-source hashes and pass the bitwise gates; downloads must be re-hashed from their public URLs.
- Only publish numbers whose engine source is committed. Today that means the 216.7 s long prompt and the ~87.7 tok/s
  four-card decode; 94.2 / 72.4 tok/s wait on decision 1.

## Next work (ranked, with sizes)

1. Once merged and approved: point `sc117-lan` at the AOT build of the merged tree with the two-card flags (16 unit
   lines, an adapter that forwards them to one-card ranks, its session compat gate). Expected ~72 tok/s and a ~2 min
   faster start (measured on lab servers).
2. Prompt reading, each 1–3% of the long prompt (see
   [prefill-balance RESULT, "What is left"](research/tp/prefill-balance-2026-10-31/RESULT.md)):
   rank 1's input upload / readback overlap (~3–5 ms per chunk); rank 0's draft chunk (13.7 ms) and its card 27
   trailing card 23 by ~9 ms; the HC split's prefill mode (in the unmerged patch, ~5 s). Rank 0 is only ~6 ms per
   chunk behind rank 1, so rank-1-only levers are capped until rank 0 also drops.
3. Decode, each ≤1–2%: shared-expert split for decode (exchange cost eats most of it), more exact glue fusions
   (obey the host-readback rule), the last runtime-indexed lookups (begin/commit/PLE glue, argmax, readback copy),
   the ~1 µs per HC GEMV launch still unexplained in production vs bench.
4. Two cards: `SC117_TARGET_SPLIT=24` (≤1%, env change only); a pipeline-side split of rank 1's head (new engine work,
   size it first with a one-card site trace).

## Ideas to explore when the above is done

- **A new structural idea for decode above ~100 tok/s.** The four-card step is ~8.7 ms with both stages balanced;
  about half of each stage is replicated or split work with a fixed per-launch part, and misses still cost ~18% of
  decode time. Measured dead ends: multi-row verification (1.42× at two rows), a persistent kernel per layer, exchange
  stores in the producer's tail, deeper speculation on today's kernels.
- **Faster experts within exactness** (instruction-bound at 26–42% of memory bandwidth): a lossless re-encoding of
  IQ2_S/IQ3_XXS/IQ3_S codes that is cheaper to decode (needs VRAM, which is nearly full; consider experts by id).
- **Correctly rounded divide/sqrt** (decision 2) and the CPU-reference disagreements.
- **Sessions/continuation and 262K context on the four-card TP layout** (sessions are still refused under TP).
- **Draft acceptance without training** (owner prohibits draft training): top-2 tree drafting needs a cheap
  multi-row pass first.
- The older ideas in [`IDEAS.md`](IDEAS.md) and [`research/pp4-review-2026-10-28/`](research/pp4-review-2026-10-28/).

## Hard-won rules (each cost real time)

- **Exactness gates:** compare against a flags-off reference over many steps, not only card 1 vs card 0. A
  scattered-peer-store race kept both cards equal and wrong ([xtail](research/tp/xtail-2026-10-31/RESULT.md)).
- **Host-readback rule:** a fusion that moves a site's write must check every host read of that site, including rank
  1's draft-input export to rank 0 (the first HC fusion broke the draft input; only the service startup gate saw it).
  The rank harness now compares exported rows.
- **Two-request case:** prefill changes must be gated prompt → decode → reset → prompt → decode; one-request gates
  missed a buffer that a reset zeroes. Use the exact-pattern ones checker
  ([`inventory_check.py`](research/tp/prefill-draft-batch-2026-10-30/inventory_check.py)).
- **Codegen:** a default-off branch inside a shared generic kernel cost 1.4% decode; always run the decode-half check
  (new binary default path vs previous binary, interleaved, within 0.3%).
- **One binary per A/B:** run both arms of an end gate on the same binary with the flag off/on.
- **Flags must reach the ranks:** the lab adapter forwards only listed keys (`TP_KEYS`, and `ONE_CARD_KEYS` in the
  two-card copy). Confirm in `/proc/<pid>/environ`.
- **Cold start:** a JIT server's first decode step compiles for 53–61 s, against the ranks' default 60 s
  `--wait-seconds`; pass 300 or use the AOT build.
- **Never** run a profiler, event profiling or `OWNRT_SITE_TRACE` with `--tp-replicate` (it faulted a card); time
  split shapes on one card (`OWNRT_TP_SHAPE_PROBE`). Class-timing sizes of tiny kernels overstate what removing them
  saves.
- **Host memory:** keep MemAvailable ≥ 64 GB (servers need ~99 GB to start); `/dev/shm` run folders count against it.
  Archive every phase to the RAID with sha256 and delete the `/dev/shm` copy. Root disk has ~29 GB free.
- **Cards are shared through** `/dev/shm/card{23,27,43,47}.lock` with bounded `flock` waits; no builds or archives
  while anyone's fresh-server timing runs. Multi-card processes need `LimitNOFILE=1048576`, `NEOReadDebugKeys=1
  EnableDeferBacking=0` and `OWNRT_TP_CARD_CONTEXT=1` under TP.
- **Permission refusals** are the owner's decision; report them, never route around them.

## How the work was run

The orchestrator delegated each lever to one background agent with a written brief (scope, gates, rules, results
folder), reviewed its reports at each gate, pushed its commits, and kept `CURRENT.md`, the README and
`own-runtime.html` in step. Agents built in private `/dev/shm` copies of `engine/src`, committed only their research
folder (and, when allowed, a default-off engine change), and never pushed. Each lever ended with one fresh-server
end gate (13-case startup gate, 12-prompt suite = B19, long-prompt outputs = reference) or was closed with a
DO-NOT-REPEAT row.
