# Current Workspace State

Last reviewed: **2026-08-20**

## Authority And Update Rule

This is the sole cross-repository authority for the loaded service, active
optimization lane, protected work, and immediate next actions. Result packets
own promoted evidence, lane handoffs own detailed resume context, and `notes/`
owns experiment chronology. Keep this file short; do not append experiment
history here.

Always verify Git status, relevant processes, listeners, and the actual endpoint
before an operational change. A recipe or installed unit does not prove that a
model is currently loaded.

The verbose pre-consolidation workspace ledger remains available in Git at
`0dbe3ab3e:CURRENT.md`. Its durable findings are also preserved in the linked
result packets, handoffs, notes, patches, and reproduction recipes below.

## Live Service

Verified on 2026-08-15:

- `muse-glimmer-bf16-fleet.service`: inactive;
- `muse-glimmer-frontdoor.service`: inactive;
- no listeners on `8000`, `18080`-`18089`, `19470`, or `19471`;
- no `llama-server`, vLLM, or frontdoor process is running.

The preserved Muse source/build remains under
`/home/steve/src/llama.cpp-muse-100`. Do not reset, clean, rebuild, restart, or
repurpose that tree without first checking service ownership and the canonical
host GPU lock; inactive services can still be started by another operator.

Operational and result references:

- [Muse BF16 service runbook](docs/muse-glimmer-bf16-service-runbook.md)
- [Muse Q8/WOQ closed result](results/muse-glimmer-30b-q8-woq-b70/README.md)
- [Muse standalone reproduction](repro/muse-glimmer-30b-q8-woq-b70-100tps-20260813/README.md)
- [Local operations and recovery policy](docs/local-ops.md)

The closed no-training Muse Q8/WOQ record remains approved by LocalMaxxing as
[`cmss8515c00n0ms01n3begqgg`](https://www.localmaxxing.com/en/runs/cmss8515c00n0ms01n3begqgg).
It is a Q8/WOQ target-verified result, not BF16/lossless or universally
token-exact evidence.

## Active Optimization Lane

Qwen3.8 27B work is active. Accepted GGUF target-only results were measured on
the two-ASRock-B70 reference host. Current AutoRound INT4 TP2 measurement uses
a selected pair from the four-B70, 125-GiB host; the two-B70, 15-GiB host is a
source/op-audit worker and must not run the full server. DFlash, MTP, prompt
reuse, and other speculation are separate result classes and remain outside
the target-only headline.

All Git work is performed directly on `main`. Do not create branches or
secondary worktrees. Use focused commits, patches, bundles, configs, and result
packets for isolation and recovery.

## Active Research: Qwen3.8 27B TP2

The promoted target-only two-B70 Q4_K_M result is:

- conventional 99-interval median: **`49.717503 tok/s`**;
- historical helper: `50.219700 tok/s`;
- full-output after-TTFT median: `49.734644 tok/s`;
- quality: 12/12 cold 512-token outputs exact against the accepted control;
- cache: `cached_tokens=0` for 12/12;
- speculation: none;
- LocalMaxxing: approved as
  [`cmsy530c70cpwms01bl1sjk6g`](https://www.localmaxxing.com/en/runs/cmsy530c70cpwms01bl1sjk6g).

The 2026-08-15 Q4_K fusion passed a clean build, mechanism counter, same-binary
control, and complete 12-prompt cold suite. It improved the conventional
median by `+1.701%`; all complete output hashes remained exact. The Q8_0 TP2
transfer separately reached `36.772932 tok/s` conventional with 12/12 matched
complete outputs. On 2026-08-16, Q8 and Q4_K_M also passed exact, arithmetic,
JSON, factual, logic, Python-result, repeat-stability, and 3,829-token needle
canaries. Q8 is the primary quality-conservative service identity; Q4_K_M is
the explicitly lower-precision speed lane.

A separate one-B70 SergioB GPTQ INT4 route was validated on 2026-08-16. Native
FP16 KV reached `34.160467 tok/s` target-only and `87.605425 tok/s` MTP4 at
p512/g128 and 8K; both beat the FP8-KV rows. MTP4 accepted 511/540 drafts,
matched the GPTQ target on the semantic suite, and its loaded draft parameters
were verified FP16. The GPTQ target itself failed the Python-result canary
(`30` rather than `14`) passed by Q8/Q4, so the lane is quality-rejected as the
default and remains experimental. The nightly patch is redundant at 8K; 131K,
the boundary patch, power, and broad quality remain open.

The official Qwen3.8 FP8 checkpoint now has a working TP2 vLLM/XPU baseline in
the newer pinned `0.27.2rc1.dev77` image. Eager decode measured `17.097358`
tok/s; a size-one PIECEWISE graph measured **`21.708532 tok/s`** with five
unique cache-zero p512/g128 requests. Seven exact canaries, eight-run
determinism, and a 3,829-token needle all matched the Q8 oracle. This is slower
than GGUF Q8 and remains experimental because vLLM officially limits XPU Graph
support to single GPU; it is the source-level GDN/collective control, not the
promoted fastest service.

Resume and evidence:

- [Qwen3.8 model board](README.md#qwen38-27b-model-board)
- [target-only pass-2 ledger](experiments/qwen38-27b-b70/notes/2026-08-15-target-only-pass2.md)
- [Q4_K_M standalone reproduction](repro/qwen38-27b-q4km-tp2-asrock-b70/README.md)
- [Q4_K fusion source increment](patches/qwen38-27b-q4km-tp2-asrock-b70/README.md)
- [Q4_K structured summary](experiments/qwen38-27b-b70/data/2026-08-15-q4km-tp2-q4k-glu-summary.json)
- [Q8 structured summary](experiments/qwen38-27b-b70/data/2026-08-15-q8-tp2-transfer-summary.json)
- [Q8 quality-conservative standalone reproduction](repro/qwen38-27b-q8-tp2-asrock-b70/README.md)
- [Q8 c2 cache-row fusion result](experiments/qwen38-27b-b70/notes/2026-08-16-q8-c2-cache-row-fusion-neutral.md)
- [Q8 distributed greedy argmax result](experiments/qwen38-27b-b70/notes/2026-08-16-q8-distributed-greedy-argmax-neutral.md)
- [community GPTQ/MTP vLLM idea](community/sergiiob-qwen38-27b-vllm-xpu/STATUS.md)
- [one-B70 GPTQ target-only graph validation](community/sergiiob-qwen38-27b-vllm-xpu/validation/2026-08-16-local-target-only-graph-validation.md)
- [one-B70 GPTQ native-MTP matrix](community/sergiiob-qwen38-27b-vllm-xpu/validation/2026-08-16-local-mtp-matrix-validation.md)
- [GPTQ quality/KV/runtime-dtype decision](community/sergiiob-qwen38-27b-vllm-xpu/validation/2026-08-16-quality-kv-dtype-decision.md)
- [official FP8 vLLM/XPU TP2 reproduction](repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/README.md)
- [official FP8 graph result](experiments/qwen38-27b-b70/notes/2026-08-16-official-fp8-vllm-graph-tp2.md)

Do not retry the built-in TP2 SYCL profiler or the unsafe root-both remote-write
prototype inherited from Qwen3.6 work. Both caused device faults/resets. Do not
overlap BMG AOT compilation, a model workload, or a large download on this
15 GiB host.

## Active Research: Qwen3.8 27B INT4 AutoRound, vLLM/XPU TP2 speculative

Opened 2026-08-18, succeeding the closed Qwen3.6 27B INT4 lane. This is a
**separate identity** from the llama.cpp Q4_K_M target-only lane above: different
runtime, different quantization, and native MTP speculative decoding. The
current working anchor uses MTP5.

Model `devan-carlin/Qwen3.8-27B-int4-AutoRound` at
`/mnt/usb-models/llm-models/qwen3.8-27b-int4-autoround-devan`, verified against
[`repro/qwen38-27b-autoround-int4-b70/manifests/model.json`](repro/qwen38-27b-autoround-int4-b70/manifests/model.json).

The current honest working anchor is **`101.170 tok/s` all-25** and `92.851`
on selection-12: the median of three margin-free MTP5 arms (`101.394`,
`100.455`, `101.170`) on GPUs 2,3. It is research evidence, not a promoted
record: pairwise token parity is only 21/25, 21/25, and 22/25.

Post-recovery dual-view-verified arms reproduced `102.132` and `102.176 tok/s`
but still agreed on only 21/25 prompts and each matched the fresh target-only
oracle on only 15/25. The target-only A/B itself agreed on 24/25. A decisive
TP1 pair then began and ended on the same byte-identical b936 compile-cache
tree, directly loaded the same outer and AOT artifacts, and agreed on only 2/4
preregistered divergence prompts. The residual problem is genuine runtime
nondeterminism; corrupted model bytes and TP2 cross-rank oneCCL/allreduce are not required
to produce it.

A preregistered six-arm, same-binary TP1 control then isolated the known
oneDNN W4A16 dirty prefill band. Pad-off produced two structured-extraction
token arrays (`G/F2/G`); pad-on was bit-identical in all three fresh-server
arms (`G/G/G`). Every arm directly loaded the same sealed graph/AOT artifacts,
left the compile-cache tree byte-identical, and passed strict model/runtime
identity gates. This meets the preregistered criterion and supports crediting
global in-band INT4 prefill padding for the observed six-arm structured flip,
but three pad-on observations do not establish lane-wide determinism, identify
target versus MTP-layer prefill, or establish full-25 TP2 determinism.

The subsequent pad-on composite TP2/MTP5 full-25 A2/B2 pair passed every
model, runtime, per-rank pad-engagement, direct-load, sealed-cache, freshness,
cleanup, and arm-A quality gate, but failed closed at **22/25** complete token
arrays. A2's final long-rollover response was catastrophically wrong from the
first token: all 512 token IDs were zero (rendered as exclamation marks), while
B2 produced the sane reference-family response. Preferred medians were
`100.916` / `101.124 tok/s`; legacy medians were `101.936` / `102.145`, but
none is promotable. A sealed C1 recurrence arm then reproduced A2's complete
512-zero final stream exactly, while SQL and factual-protocol each produced a
third token family. The pad fixes the scoped TP1 contrast, not full TP2
determinism. A preregistered target/verifier post-forward synchronization arm
then did not produce the zero stream, but reproduced a previously observed
unsynchronized long-rollover family,
matching B2 only through generated token 468 before splitting at token 469;
SQL and factual-protocol differed from every A2/B2/C1 family. The broad
completion boundary is insufficient and S2 is forbidden. The subsequent
bounded prompt-24 replay microscope M1 is invalid and closed: its anchored
filter used the unsuffixed public request ID, while the worker saw that ID plus
an eight-hex internal suffix, so no trace file was produced. Prompt 6 also
ended at 68 tokens, independently invalidating the strict metric window and
preventing the formal sealed checker. M1's prompt-24 tokens matched S1 only as
report-only recurrence evidence. Preserve M1 exactly and do not retry it.

A distinct raw-op native-SYCL GDN prefill/state screen then passed all 240
qualification and 12,288 main calls at the exact production prompt lengths 83,
61, and 849. Both cards, isolated/queued modes, and four separately invoked
process/order rotations were bit-identical. This is a valid bounded negative
for the frozen synthetic direct-op surface only; it does not clear real projected values, the
server, graph, scheduler, allocation-history, TP2 interleaving, or speculative
state paths.

The preregistered graph-replay-bypass R1/R2 pair then matched on all **25/25**
complete token arrays under the combined treatment: full-width speculative
target-verifier replay was bypassed, drafter graph keys were disabled, drafter
geometry changed from padded M6 to unpadded M1, and startup graph allocation
history changed. Both arms passed the sealed cache/identity/engagement gates;
R1 passed quality and R2 used immutable R1 as its peer. Prompt 24 matched the
sane S1/target-A family, but each arm matched target A on only 18/25 and B2 on
22/25. The pair's preferred central value was only `56.363 tok/s`, **44.263%**
below B2. This is a bounded positive for the combined diagnostic treatment,
not component localization, target exactness, lane-wide determinism, or a
promotable performance result. The preregistered campaign is complete and no
further arm is authorized.

The subsequent target-only split is also complete and terminal. It set the
request-selected target/verifier replay selector to N=1 while keeping the
umbrella bypass off, drafter graph keys enabled at PIECEWISE/M6, and both
startup capture descriptors intact. T1 passed all gates and quality; T2 passed
all arm-local gates but failed the mandatory peer check at **24/25**, differing
only at prompt 24 generated token 469. At prompt 24, T1 produced the sane B2
family and T2 the sane R1/R2/S1/target-A family. The pair central value was only
`60.938 tok/s`, 39.739% below B2. Target/verifier request-selected replay bypass alone
is therefore insufficient for full-25 repeatability. No T3 or retry is
authorized, and the remaining drafter-geometry/startup-history components are
not localized.

The published `101.922` MTP5 and `100.497` MTP4 LocalMaxxing rows are
invalidated and withdrawal is recommended. Both opted into a `0.03125` greedy
margin that changed emitted text on 18/25 prompts; their quality baseline used
the same margin and therefore could not detect it. Their published scratch
flag is also wrong: the historical harness silently ran with persistent
scratch enabled. The API has no amendment/deletion method, so the upstream
annotation/withdrawal still requires human contact with LocalMaxxing.

The four-card measuring host's xe driver was recovered on 2026-08-20 without
FLR or reboot and passed per-card compute, peer access, four-rank XCCL, and a
known-good exact generation canary. The launch harness now fails closed unless
the model's complete direct-I/O and ordinary cached views both match the
manifest immediately before vLLM starts.

- [lane setup and rationale](repro/qwen38-27b-autoround-int4-b70/README.md)
- [baseline evidence](data/qwen38-27b-autoround-int4-baseline-20260818.json)
- [measuring-host recovery](experiments/qwen38-27b-b70/notes/2026-08-20-measuring-host-xe-recovery-and-health-gate.md)
- [post-recovery TP1 result](experiments/qwen38-27b-b70/notes/2026-08-20-postrecovery-marginfree-tp1-runtime-nondeterminism.md)
- [INT4 prefill-pad causal screen](experiments/qwen38-27b-b70/notes/2026-08-20-int4-detpad-tp1-causal-screen-result.md)
- [pad-on composite TP2 full-25 preregistration](experiments/qwen38-27b-b70/notes/2026-08-20-detpad-composite-tp2-full25-prereg.md)
- [pad-on composite TP2 full-25 result](experiments/qwen38-27b-b70/notes/2026-08-20-detpad-composite-tp2-full25-result.md)
- [pad-on TP2 full-25 recurrence result](experiments/qwen38-27b-b70/notes/2026-08-20-detpad-tp2-full25-recurrence-result.md)
- [post-forward synchronization result](experiments/qwen38-27b-b70/notes/2026-08-20-detpad-tp2-postforward-sync-result.md)
- [bounded prompt-24 replay-microscope preregistration](experiments/qwen38-27b-b70/notes/2026-08-20-detpad-tp2-replay-microscope-prereg.md)
- [bounded prompt-24 replay-microscope invalid result](experiments/qwen38-27b-b70/notes/2026-08-20-detpad-tp2-replay-microscope-result.md)
- [native-SYCL GDN prefill/state preregistration](experiments/qwen38-27b-b70/notes/2026-08-20-native-gdn-prefill-state-stability-prereg.md)
- [native-SYCL GDN prefill/state result](experiments/qwen38-27b-b70/notes/2026-08-20-native-gdn-prefill-state-stability-result.md)
- [graph-replay-bypass preregistration](experiments/qwen38-27b-b70/notes/2026-08-20-detpad-tp2-graph-replay-bypass-prereg.md)
- [graph-replay-bypass result](experiments/qwen38-27b-b70/notes/2026-08-20-detpad-tp2-graph-replay-bypass-result.md)
- [target/verifier request-selected replay-bypass preregistration](experiments/qwen38-27b-b70/notes/2026-08-20-detpad-tp2-target-verifier-request-replay-bypass-prereg.md)
- [target/verifier request-selected replay-bypass result](experiments/qwen38-27b-b70/notes/2026-08-20-detpad-tp2-target-verifier-request-replay-bypass-result.md)

## Closed: Qwen3.6 27B INT4 AutoRound, vLLM/XPU TP2 speculative

Closed 2026-08-18. The retained LocalMaxxing row `95.384867741895 tok/s`
(12-prompt suite, `cmrh35ct50092mj01h7jgydqj`) stands and is **not** superseded.
The closing campaign reached `94.710 tok/s` all-25 / `89.766` on the record's own
suite, so nothing beat the record like-for-like and no new row was submitted.

Two durable conclusions: complete-token parity against a differently-configured
reference is unsatisfiable at fp16 on this stack, and XPU batch invariance is
dead code behind `is_cuda_alike()` gates. Do not reopen with further flag sweeps.

- [closeout analysis](notes/2026-08-18-qwen36-int4-determinism-speed-tradeoff.md)
- [closeout source packet](patches/qwen36-27b-autoround-int4-b70/determinism-closeout-20260818/README.md)
- [reproduction](repro/qwen36-27b-autoround-int4-b70-determinism-20260818/README.md)

## Protected Work And Artifacts

Preserve these paths and inspect their status before any build, cleanup, or
service change:

- `/home/steve/src/llama.cpp-muse-100`: preserved source/build used by the inactive Muse fleet;
- `/mnt/fast-ai/src/llama.cpp-q38-q4k-glu-tp2`: accepted Qwen3.8 Q4_K_M source at
  `a4349bcee`; preserve its intentional three-file uncommitted fusion delta;
- `/mnt/fast-ai/src/llama.cpp-q38-q4k-glu-tp2/build-sycl-aot-bmg-g31-oneapi-2026.1.1`:
  accepted oneAPI 2026.1.1 BMG-G31 AOT build;
- `/mnt/fast-ai/llm-models/qwen3.8-27b-gguf/`: accepted Qwen3.8 GGUF targets and MTP sidecars;
- `/mnt/fast-ai/llm-models/qwen3.8-27b-fp8/`: official FP8 artifact retained for the separate vLLM lane;
- `/mnt/fast-ai/bench-results/qwen38-official-fp8-vllm-xpu-20260816/`:
  official FP8 eager/graph/P2P controls, final quality gate, cache-zero result,
  runtime capture, and post-run health evidence;
- `/mnt/fast-ai/llm-models/qwen3.8-27b-gptq-int4-mtp/`: hash-verified
  SergioB GPTQ INT4 target with 15 BF16 MTP tensors; community replay lane;
- `/mnt/fast-ai/bench-results/qwen38-q4km-asrock-b70-20260815-pass2/`:
  accepted Q4_K fusion A/B and cold-suite evidence;
- `/mnt/fast-ai/bench-results/qwen38-gptq-int4-asrock-b70-20260816/`:
  SergioB target-only eager/graph validation, failed conservative-U graph
  attempt, logs, inspect records, prompts, and raw SSE evidence;
- `/mnt/fast-ai/bench-results/qwen38-gptq-quality-20260816/`: native/FP8 KV,
  semantic quality, MTP runtime-dtype, Q8/Q4 controls, and reset-window evidence;
- `/mnt/fast-ai/src/llama.cpp-q8-tp2-directq8-isolated`: current accepted Qwen TP2 source;
- `/mnt/fast-ai/src/llama.cpp-q38-tp2-distributed-greedy-directq8`: closed
  exact distributed-argmax candidate; preserve for mechanism reuse only;
- `/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260816-distributed-greedy/`:
  position-balanced reasoning-off controls/candidates and exact output oracle;
- `/mnt/fast-ai/src/llama.cpp-mndodd-intel-sycl`: prior accepted Qwen TP2 source; preserve as control;
- `/mnt/fast-ai/llm-models/qwen3.6-27b-q8_0-gguf/`: accepted Qwen model;
- `/mnt/fast-ai/bench-results/qwen36-q8-asrock-b70-20260813-tp2-fusion/`:
  promoted Qwen evidence and bounded negatives;
- `/mnt/fast-ai/bench-results/qwen36-q8-asrock-b70-20260814-40tps/`:
  Qwen pass-1/pass-2 evidence and current clean result;
- `experiments/qwen27_graphsafe_flash_attention/`: graph-safe INT4 source and
  generated research state;
- `experiments/qwen36-27b-autoround-int4-b70/`: INT4/MTP research packet and
  diagnostic artifacts.

Large ignored Qwen artifacts may be archived only after a complete inventory,
hash verification, and a recorded restore path. Never use broad `git clean` or
delete tracked experiment material to make the tree look tidy.

## Paused And Bookmarked Lanes

- [Qwen family map](docs/qwen36-research-map.md)
- [Muse-Glimmer-30B Q8/WOQ](results/muse-glimmer-30b-q8-woq-b70/README.md)
- [Laguna S 2.1 INT4](results/laguna-s-2.1-int4-b70/README.md)
- [DeepSeek V4 Flash K160](results/deepseek-v4-flash-k160-b70/README.md)
- [Gemma 4 26B A4B Q8](results/gemma4-26b-a4b-q8-b70/HANDOFF.md)
- [MiniMax M2.7 INT4](results/minimax-m27-int4-autoround-b70/README.md)
- [all model efforts](docs/model-effort-index.md)
- [promoted performance scoreboard](results/scoreboard.md)

These are reproducible or resumable lanes, not claims about the currently
loaded service.

## Immediate Manager Actions

1. Preserve the inactive Muse fleet and its source; verify service/process state
   again before every GPU launch.
2. Continue Qwen3.8 Q8_0 target-only TP2 from the accepted source snapshot,
   with same-binary controls, the fixed cold gate, and the semantic suite. Aim
   for 40 tok/s without weakening weights, KV precision, or arithmetic gates.
   The 2026-08-16 device-local Q8 gate/up/SwiGLU experiment is closed at
   `-0.224974%` after restoring its downstream Q8 producer; retain the
   [negative packet](experiments/qwen38-27b-b70/notes/2026-08-16-q8-fused-mmvq-swiglu-negative.md)
   and do not enable its default-off door in the accepted recipe.
   The c2 cache-row state-I/O fusion is also closed: it gained `+5.355%` in
   synthetic batched-bench but converged to the same endpoint plateau and did
   not satisfy strict cross-batch output invariance. Preserve the
   [neutral packet](experiments/qwen38-27b-b70/notes/2026-08-16-q8-c2-cache-row-fusion-neutral.md)
   without adding its aggregate rate to the promoted board.
   Distributed greedy argmax is closed as exact but neutral: the
   position-balanced primary delta was `-0.057%`, full-output rate was
   `+0.342%`, and TTFT regressed `+8.311%`. Preserve its
   [packet](experiments/qwen38-27b-b70/notes/2026-08-16-q8-distributed-greedy-argmax-neutral.md)
   and only revisit if winner selection can avoid the added cross-queue sync.
3. Keep full Qwen3.8 AutoRound server runs off the 15-GiB host. The recovered
   four-B70 host's pad-on composite TP2 pair passed its sealed identity and
   quality gates but failed 22/25 A/B parity, including one all-zero 512-token
   response. The exact C1 recurrence arm also passed every sealed gate and
   repeated that all-zero response byte-for-byte while producing third SQL and
   factual families. With post-target-forward synchronization active, S1 did
   not produce the zero stream, but reproduced a prior unsynchronized family,
   still split from B2 at token 469, and produced further SQL/factual families.
   The bounded request-filtered M1 then failed engagement because vLLM's worker
   request ID had an unaccounted eight-hex suffix; no trace was written. Prompt
   6 also stopped at 68 tokens, so the count-24 displayed median is invalid and
   the formal sealed checker did not run. Preserve A2/B2/C1/S1/M1, run neither
   D nor S2, and do not retry M1. The distinct raw native-SYCL GDN prefill/state
   screen is now closed as a valid bounded negative after 12,528 clean calls.
   The subsequent graph-replay-bypass R1/R2 pair passed all sealed gates and
   matched on 25/25 token arrays, but only under a combined treatment that also
   changes drafter geometry and startup allocation history. Its preferred
   central value was `56.363 tok/s`, 44.263% below B2, and each arm remained
   only 18/25 exact versus target A. Treat it as bounded diagnostic evidence,
   not a fix or performance candidate; preserve both arms and run no further
   arm under that preregistration. See the
   [recurrence result](experiments/qwen38-27b-b70/notes/2026-08-20-detpad-tp2-full25-recurrence-result.md),
   [sync result](experiments/qwen38-27b-b70/notes/2026-08-20-detpad-tp2-postforward-sync-result.md),
   [microscope preregistration](experiments/qwen38-27b-b70/notes/2026-08-20-detpad-tp2-replay-microscope-prereg.md),
   [invalid microscope result](experiments/qwen38-27b-b70/notes/2026-08-20-detpad-tp2-replay-microscope-result.md),
   [native-GDN preregistration](experiments/qwen38-27b-b70/notes/2026-08-20-native-gdn-prefill-state-stability-prereg.md),
   [native-GDN result](experiments/qwen38-27b-b70/notes/2026-08-20-native-gdn-prefill-state-stability-result.md),
   [graph-replay-bypass preregistration](experiments/qwen38-27b-b70/notes/2026-08-20-detpad-tp2-graph-replay-bypass-prereg.md),
   and [graph-replay-bypass result](experiments/qwen38-27b-b70/notes/2026-08-20-detpad-tp2-graph-replay-bypass-result.md).
   The separately preregistered
   [target/verifier request-selected split](experiments/qwen38-27b-b70/notes/2026-08-20-detpad-tp2-target-verifier-request-replay-bypass-result.md)
   is now closed as a terminal negative: T1/T2 passed every arm-local gate but
   matched only 24/25 complete token arrays, at the known prompt-24 token-469
   split. Preserve both arms, run no T3 or retry, and do not promote or submit
   these speeds. Any drafter-geometry or startup-history split needs a new
   source audit and preregistration.

   The TP-safe draft-INT4 margin qualification is now closed as a terminal
   negative. All 598 real TP2 records exceeded the strict `<0.125` error bound,
   maximum observed error was `2.375`, and the repaired gathered argmax still
   differed from full FP16 on 9 calls. Q1 also failed its preregistered pad
   marker gate, so run no retry, margin sweep, or full-25 arm. Its timing is
   invalid by construction. Clock locking is separately closed as neutral: the
   local draft-head M1 operator changed only `+0.171%` at fixed 2800 MHz and M6
   was flat, while the earlier endpoint bracket was `-0.487%`. See the
   [qualification result](experiments/qwen38-27b-b70/notes/2026-08-20-draft-margin-tp2-qualification-result.md)
   and [clock/operator screen](experiments/qwen38-27b-b70/notes/2026-08-20-draft-head-clock-and-row-scaling-screen.md).
   The next AutoRound research surface is the packed MTP target/verifier
   FlashAttention block. Build and pass a bounded M6/head-256 operator
   qualifier before changing a server binary or authorizing another full-25
   arm; the [exact-shape operator preregistration](experiments/qwen38-27b-b70/notes/2026-08-20-qwen38-mtp5-m6-fa-operator-prereg.md)
   is implemented but not yet launched. The two-B70, 15-GiB host remains
   source/op-audit only under this local four-B70 contract.
4. Use the official FP8 graph repro as the vLLM control and target its Triton
   GDN/state-I/O and TP2 synchronization path; simple oneCCL P2P access is
   already closed as neutral. Preserve the 9/12 GiB host cgroup.
5. Keep SergiioB's single-card GPTQ/MTP vLLM recipe experimental: it is fast,
   but the checkpoint failed the no-quality-loss semantic gate. Never stop a
   vLLM XPU container before `/health` during graph initialization.
6. The 49.717503 tok/s Q4_K_M target-only result is submitted and approved as
   LocalMaxxing `cmsy530c70cpwms01bl1sjk6g`; do not resubmit it unchanged.
7. Keep `main` synchronized before and after focused commits. Preserve failed
   experiments as patches and notes rather than branches or worktrees.
8. Archive large ignored Qwen artifacts only through the verified manifest and
   restore procedure linked from the Qwen family map.
9. Treat DFlash 2 as a separate future llama.cpp/GGUF lane. Upstream PR #27342
   is still open, initial evidence is single-device and workload-sensitive, and
   no compatibility with this vLLM AutoRound TP2 identity is established. See
   the [intake note](experiments/qwen38-27b-b70/notes/2026-08-20-dflash2-future-lane-intake.md).
10. The only interesting new LocalMaxxing mechanism is runtime INT4 over five
    MTP draft linears. The author-linked patch is public, but four of its five
    runtime linears are already packed INT4 in this checkpoint; only `mtp.fc`
    remains BF16. Its likely TP2/MTP5 headroom is roughly `0.5`–`1.0 tok/s`, so
    op-screen the narrow port before considering a server arm. Ignore aggregate
    C5/C32 rows as single-stream leads. See the
    [feed audit](experiments/qwen38-27b-b70/notes/2026-08-20-localmaxxing-qwen38-external-lever-intake.md).
