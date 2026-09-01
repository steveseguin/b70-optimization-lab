# Current Workspace State

Last reviewed: **2026-08-31**

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

Verified on 2026-08-31:

- `muse-glimmer-bf16-fleet.service`: inactive;
- `muse-glimmer-frontdoor.service`: inactive;
- no listeners on `8000`, `18080`-`18089`, `19470`, or `19471`;
- no Qwen benchmark listeners on `18110`-`18129`;
- no `llama-server`, vLLM, or frontdoor process or container is running.

## Active Qwen3.8 AutoRound INT4 Two-B70 Optimization

The active local lane is the dense Qwen3.8-27B AutoRound INT4 checkpoint on
the two B70s. Medium-prefill nondeterminism was localized to INT4 projection
shapes and repaired with the repository-owned M=512 projection hook. Four
fresh traced processes matched at every decoder boundary. Two strict TP1/MTP0
runs then reproduced all 12 complete varied-prompt token streams; removing the
diagnostic device-wide barriers reduced median TTFT from 380.687 ms to
310.378 ms (18.47%) without changing any token. The corrected MTP0 rates,
24.80 tok/s TP1 and 18.07 tok/s TP2, are correctness baselines—not promoted
speed recommendations.

TP2/MTP1 attempts D61 and D62 both loaded the target and drafter but lost TP
rank 1's Level Zero device during vLLM's profile run, before serving any
request. D62 ran after a full reboot and independent compute gates on both
B70s. Its explicit synchronization first surfaced the error at entry to a
dense MLP, before the dummy sampler, while Xe logged 594 unsuccessful fault
responses, 27 CCS engine-memory CAT errors, and one CCS reset on PCI function
`0000:e3:00.0`. Both B70s returned to normal state and passed independent
compute after teardown. D63 disabled the M=512 projection repair and
reproduced device loss on both ranks, but its stage-localization verdict is
formally inconclusive: the runner's `/instrument` `PYTHONPATH` displaced the
diagnostic image's `/workspace/vllm` source, so the frozen sampler receipt gate
could not be satisfied. Both B70s again passed independent compute after
teardown. D64 used immutable image
`sha256:a1454ebe...cc13c` and an explicit
`/workspace/vllm:/instrument` import path. It adds per-layer synchronization
around the attention/GDN mixer, collectives, normalization, and MLP while
keeping projection repair off. D64 reached readiness with exact complete
decoder accounting and no Xe event, but the runner expected one sampler pass
per rank while vLLM performs two; it therefore stopped before the required
second health check and remains a literal cardinality false-fail. D65 repeated
the exact arm with the corrected cardinality and passed: 2,080/2,080 decoder
boundaries completed, every sampler stage produced exactly four receipts, both
health checks passed, and the timestamp-bounded kernel log was clean. This
confirms enforced decoder ordering prevents the startup device loss. D66 then
scoped those barriers to `GPUModelRunner.profile_run()`: its one true profile
forward completed exactly 1,040 boundaries, the later unsynchronized warmup
forward also completed, and the API reached readiness with a clean kernel log.
It remains a literal receipt-count false-fail because its frozen contract
expected both forwards to be profile forwards. D67 changes only that expected
count from 2,080 to 1,040 and passed both health checks with a clean kernel
delta. These arms are startup-only and cannot yield a performance claim. D68
restores projection repair and runs the full strict suite against the frozen
TP2/MTP0 token oracle; its post-request log gate was designed to prove the
decoder receipt count remained 1,040. D68 instead failed before readiness at
layer 1's repaired dummy MLP: the M=512 hook padded synthetic 256-token profile
data and Xe logged 491 fault responses, five CAT errors, and one reset. Both
B70s recovered and passed independent deterministic compute after teardown.
D69 marked all `_dummy_run` calls and bypassed projection repair only for those
synthetic inputs; it passed exact startup accounting, both health checks, and a
clean kernel gate with repair enabled. Real request prefills retain the repair.
D70 passed startup and began the first strict request, then rank 1 lost its
device asynchronously before the first response completed; no performance row
exists. Xe logged 513 fault responses, seven CAT errors, and one reset. A
post-teardown matrix health probe then hung and added a GPU0 BCS fault, so the
host required a reboot before D71. D71 enabled the hook's existing barriers
and localized the first-request loss exactly to the rank-1 M=512 padded dense
`down_proj`; the following sync surfaced device loss. The prior M=128 option is
not viable because D58 already proved a response-token change. D72 is the clean
post-reboot control: full strict TP2/MTP1 with the now-proven startup fix but
projection repair disabled. It must still match the frozen MTP0 oracle or fail.
See the
[`D62 result`](experiments/qwen38-27b-b70/notes/2026-08-31-qwen38-prefill-projection-repair-tp2-mtp1-sync-d62-result.md)
[`D63 result`](experiments/qwen38-27b-b70/notes/2026-08-31-qwen38-tp2-mtp1-no-projection-repair-startup-d63-result.md),
and
[`D65 result`](experiments/qwen38-27b-b70/notes/2026-08-31-qwen38-tp2-mtp1-decoder-stage-sync-d65-result.md).

## Qualified Qwen3.8 One-Card Package Work

The strict Q4_K_M target plus external Q4_0 MTP-draft screen is complete.
MTP2 is the qualified one-card mode at **42.636988 tok/s**, the median of two
fresh-server class-balanced 12-prompt/512-cap suites. It is 55.75% faster than
the same-build MTP0 control (`27.375682 tok/s`); both replicas passed cache-zero
and objective-canary gates and matched all 12 complete MTP0 token arrays. MTP5
matched 0/12 and is rejected. The package and exact replay are in
[`packages/qwen38-27b-q4km-mtp2-tp1-b70/`](packages/qwen38-27b-q4km-mtp2-tp1-b70/)
and [`repro/qwen38-27b-q4km-mtp2-tp1-b70/`](repro/qwen38-27b-q4km-mtp2-tp1-b70/).

Do not reuse the target-only context or concurrency values for this deployment.
The new MTP2 context campaign directly measured unrepeated technical prose,
Python code, and structured documentation at exact 2K-32K depths. Across two
fresh MTP2 servers, all 36/36 outputs matched a fresh same-build MTP0 oracle;
the three-class/two-server 32K aggregate is **36.505065 tok/s** with
**39.538 s TTFT**. This is Grade-B real-content context-shape evidence, not a
natural retrieval/task suite. The older repeated-token diagnostic remains a
real 2K/token-23 divergence, so MTP2 parity is workload-scoped rather than
universal. The output-qualified HTTP concurrency campaign is also complete:
the first viable
one-B70 MTP2 capacity was 16 slots/8K total context, where two fresh servers
measured **68.341 aggregate tok/s at 16 users** and 256/256 concurrent
exact-answer canaries passed. The 32-slot/16K and 64-slot/16K or 32K profiles
failed startup with device OOM. Multi-user greedy output remains
batch-shape-dependent, so this is output-isolation-qualified. Natural
retrieval/task long-context evidence remains open. No benchmark process is
currently live.

The quality-conservative one-card Q8_0 target now also has a separately
qualified short-context Q4_0-draft MTP2 package. Two fresh servers measured
**37.062028 tok/s** versus **19.582597 tok/s** for the configuration-matched
MTP0 control (**+89.26%**); all 24/24 MTP2 arrays matched control, cache stayed
zero, and every objective canary passed. MTP1 passed at 30.260758 tok/s but was
slower. This profile used only 1,024 configured context tokens: its 32K and
concurrency cells remain unmeasured and no target-only value transfers. The
package and replay are in
[`packages/qwen38-27b-q8-q4mtp-mtp2-tp1-b70/`](packages/qwen38-27b-q8-q4mtp-mtp2-tp1-b70/)
and
[`repro/qwen38-27b-q8-q4mtp-mtp2-tp1-b70/`](repro/qwen38-27b-q8-q4mtp-mtp2-tp1-b70/).

The two-card Q4_K_M target now also has a separately qualified short-context
Q4_0-draft MTP2 package. Two fresh candidate servers measured `64.180644` and
`64.293959 tok/s`; their class-balanced median is **`64.237301 tok/s`**, or
29.02% above the matched fresh MTP0 oracle at `49.787366 tok/s`. All 24/24
complete candidate arrays matched the unchanged oracle, cache stayed zero, and
every objective canary passed. This result does not inherit the target-only
32K or concurrency profiles. The exact replay is in
[`repro/qwen38-27b-q4km-q4mtp-mtp2-tp2-b70/`](repro/qwen38-27b-q4km-q4mtp-mtp2-tp2-b70/).

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

## Active Upstream-Current XPU Integration Policy (2026-08-23)

The active development target is a fresh custom build from the literal vLLM
and vLLM XPU-kernel upstream `main` heads, resolved immediately before every
integration build. A published `nightly` image is not current when either
source head is ahead of it. In that case the image is only a runtime base and
an official-image comparison lane; it never substitutes for the current-main
source identity.

The last qualified official-image comparison was the rolling tag
`vllm/vllm-openai-xpu:nightly`, pulled and resolved on 2026-08-23 to the
immutable repository digest
`sha256:d3f5daa1552a231471a5ec5097475d282e07788db336819ed9e932f9193b0e35`.
The image was created `2026-08-23T05:09:33.938169411Z` and contains:

- vLLM source `a3561ef8e49d3545c4078df43444beb4c98ae124`, package
  `0.26.1rc1.dev1120+ga3561ef8e.xpu`;
- Torch `2.13.0+xpu`, Triton `3.7.2+xpu`, transformers `5.15.0`, and
  vLLM XPU kernels `0.1.13.2`;
- 18 vLLM commits after the certified `e9d1398d9` image below.

This official-image identity remains the last qualified comparison base. Its
complete MTP0/F16/graph column is correctness- and quality-qualified at
TP1/2/4, but it is not a wholesale performance replacement for the pinned
frontier below and is not proof of literal current-main behavior. TP1 strict
repeated about 0.22% slower, TP2 strict was 1.08% slower, and a TP4 strict
71.9002 high fell to 71.2457 on an exact same-cache repeat. The pinned
`30.2178 / 48.8301 / 71.5488` diagnostic runs, whose corresponding captured
highs are `30.2569 / 48.950458800865434 / 71.6741`, used an unmodified official
image: no local vLLM patch, XPU-kernel patch, source mount, DSO overlay, or
image mutation was hidden in that result. Its optimization overlay is the
exact graph, container IPC, device-selection, cache-isolation, model, memory,
and benchmark contract. Carry that contract forward first; do not lower or
relabel any historical speed while current main is being qualified.

The most recent completed custom-source qualification used vLLM
`0ecc284790e5403f74b899524ef82ecb69f83cb3` on the official base. Its
stock-base-kernel control passed the full TP1 contract at
`30.282673 / 30.324298 / 30.325971 tok/s` (diagnostic / strict A / strict B),
including all quality, model, source, benchmark-shape, and sealed-cache gates.
Treat this as a qualified dated 0ecc profile, not as proof that 0ecc remains
literal current after the run. Independent remote ref and registry checks at
`2026-08-24T09:14:47Z` still resolved 0ecc, `baaa05bb4e`, and the same
official digest. A later mandatory freshness gate resolved vLLM `main` to
`e239947777e18071c8053195ce599b6511717f67`; XPU-kernel main and the official
nightly digest remained unchanged. Before e239 was built, another mandatory
gate resolved `main` to `79bb395eea64dbfef99a55f010d2854db71f8571`.
The intervening commits change Cohere serving and pooling-only paths, not Qwen
generation, XPU, speculative decode, graph/autotune, distributed runtime,
dependencies, or Rust. A zero-source-overlay `--build-all` completed from
79bb with both the stock-base-kernel control and exact-current-kernel
`baaa05bb4e` image; all static receipts pass, but GPU qualification is still
pending. See the [79bb build receipt](experiments/qwen38-27b-b70/data/2026-08-24-qwen38-79bb395eea-absolute-current-main-build.json).

The paired vLLM-0ecc/current-kernel-`baaa05bb4e` candidate passed correctness
and quality but missed both strict speed gates at
`30.293320 / 30.279196 / 30.261661 tok/s`. It is not promoted and does not
authorize TP2/TP4. The small stock/current-kernel difference is not yet causal
proof because each lane had an independent fresh autotune realization and the
order was fixed. Preserve the complete failed candidate and the qualified
stock-kernel control; resolve newest upstream again, forward-port the explicit
runtime/decision overlays, and requalify without lowering any historical
floor. See the [structured campaign evidence](experiments/qwen38-27b-b70/data/2026-08-24-qwen38-0ecc-tp1-qualification-attempts.json).

Attribution found identical graph/code/compiler/config/environment identities
and 38/38 compatible decision paths, but 17 different normalized autotune
winners. Before the decision-only program ran, the host hard-rebooted from
`7.0.0-28-generic` into `7.0.0-30-generic`; no overlay arm was active. The
0ecc packet program then closed stale before launch when vLLM advanced to
e239; the hardware gate and all overlay arms remained unrun. Its exact 38
decisions are preserved as historical source evidence and must not be
relabeled as e239 or 79bb.

The first atomic 79bb attempt then closed before any candidate image, model,
cache, or benchmark ran. Four-card identity, per-card compute, and the
four-device peer oracle passed; the host-only XCCL probe mixed the May
virtualenv's Torch/SYCL/oneCCL with the system oneAPI-2026 UR loader, and all
four ranks segfaulted at the first barrier. The 54-file raw manifest verifies.
This is failed-incomplete infrastructure, not 79bb correctness or speed
evidence, and it changes no protected result. See the
[failure record](experiments/qwen38-27b-b70/notes/2026-08-24-qwen38-79bb-hardware-gate-mixed-runtime-failure.md).

R2 corrected the host gate and passed it completely: coherent runtime,
four-card identity/compute/peer/XCCL, clean journal and taint, and clean
postflight. The wrapper then false-failed its first frozen-input check before
starting the candidate. GNU `cmp -s` trusted the procfs boot ID's reported size
of zero and rejected its byte-identical 37-byte snapshot; ordinary comparison
and both SHA-256 values prove the boot never changed. The r2 campaign has only
sealed inputs and all three arms are missing, so it is also failed-incomplete
infrastructure with no performance effect. See the
[r2 closeout](experiments/qwen38-27b-b70/notes/2026-08-24-qwen38-79bb-r2-procfs-boot-validator-failure.md).

R3 then passed the fresh hardware gate and ran two clean zero-overlay arms.
The diagnostic arm passed at `30.25266152916977 tok/s`. Strict replay A passed
its canary, 25-row natural-EOS benchmark, immutable-cache check, full exact
quality battery, and clean shutdown, with an observed median of
`30.2372362888838 tok/s`. Before the wrapper could write its strict speed gate,
the mandatory post-arm freshness check found that vLLM `main` had advanced
from 79bb to `9f295fe8cee4cbd2b21a5ce3066cec026e4bd2af`; XPU-kernel main and the
official nightly digest were unchanged. The strict runner correctly wrote
`stale-before-promotion`, exited 5, and prevented replay B. R3 is therefore
failed-incomplete/stale, not a completed speed regression or a qualification;
its observed strict value cannot authorize a compatibility packet or lower a
protected result. Both roots are sealed and all cleanup guards passed. See the
[closed 0ecc preregistration](experiments/qwen38-27b-b70/notes/2026-08-24-qwen38-0ecc-tp1-control-decision-overlay-prereg.md),
[r2 preregistration](experiments/qwen38-27b-b70/notes/2026-08-24-qwen38-79bb-untreated-tp1-r2-prereg.md), and
[r3 closeout](experiments/qwen38-27b-b70/notes/2026-08-24-qwen38-79bb-r3-stale-during-replay-a.md).

The successor zero-overlay build completed at vLLM
`4ca856b0b59d87c7b167d1bd8c748421719c9a57`, XPU-kernel main
`baaa05bb4e92901219a5a072dd63f2474896f6d1`, and the unchanged official
nightly digest. Both the stock-kernel attribution image and both-current image
passed static certification. Before any hardware gate, container, model, or
GPU arm launched, the independent prelaunch audit resolved vLLM `main` to
`ecfa7bb37316a3c1dab345fea4178d81f63b1ce4`. The 4ca packet therefore closed
stale and unlaunched. Its one-commit successor caches common multimodal token
sequences; none of the changed files is on this dense text-only Qwen path, but
that bounded audit does not waive a newest-head rebuild or qualification. See
the [4ca build record](experiments/qwen38-27b-b70/notes/2026-08-24-qwen38-4ca856b0b5-absolute-current-main-build.md)
and [closed R1 preregistration](experiments/qwen38-27b-b70/notes/2026-08-24-qwen38-4ca856b0b5-untreated-tp1-r1-prereg.md).

The preservation manifest binds the dated 4ca zero-overlay build to **zero**
applied decision files and **zero** carried compiled outputs while retaining the
verified TP2 78-decision artifact and accepted TP4 152-decision performance
overlay separately. Neither was silently dropped or baked into the unlaunched
R1; after a successor passes TP1, compatible decisions require
exact-path/config-hash remapping into a fresh compile and full TP2/TP4
qualification. The qualified 0ecc stock
control `30.282673 / 30.324298 / 30.325971` profile is also explicitly
protected. Unused build cache was pruned, and the removed local 79bb and 4ca
images are exactly Docker-loadable from their verified USB archives. The
redundant 4ca build root was moved beside its archive; no unique evidence was
deleted.

The next two literal-current builds completed both zero-overlay images and all
static checks at ecfa and then f620. Each exhausted root space only while
writing the final aggregate receipt, after the image exports and checks. The
exact two-image pairs and complete build roots were moved to USB, verified, and
only then removed locally. No GPU was exposed. The f620 receipt is explicitly
marked as recovered from immutable labels/hashes rather than as a normal
builder finalization. vLLM `main` subsequently advanced through 4c56 to
`29c9af5211e618bfb78c4140db9e814f1a838aa7`; kernel main and the nightly digest
remained unchanged. Both builds are therefore stale and never launched. See the
[closeout](experiments/qwen38-27b-b70/notes/2026-08-24-qwen38-ecfa-f620-build-closeouts.md),
[ecfa attempt](experiments/qwen38-27b-b70/data/2026-08-24-qwen38-ecfa7bb373-absolute-current-main-build-attempt.json),
and [f620 recovered receipt](experiments/qwen38-27b-b70/data/2026-08-24-qwen38-f620499ee3-absolute-current-main-build.json).

The next builder invocation resolved a still-newer literal head,
`7797b6022c129b862e45ae6aed08822e65d1bccb`, and completed both zero-overlay
images, the normal aggregate receipt, archive copy, checksum battery, and
post-archive freshness seal. Kernel main and the nightly digest remain baaa and
3ee0. The new commit's per-architecture batch-invariant matmul tables activate
only for BF16 plus `VLLM_BATCH_INVARIANT` on CUDA Ada/Hopper; this F16 XPU lane
does not enable that mode and resolves the prior default. Do not report the
upstream "~3x" title as a B70 gain.

After pruning only unused builder cache, root headroom is about 14.0 GiB, above
the unchanged 12-GiB GPU launch floor. The exact
[7797 build receipt](experiments/qwen38-27b-b70/data/2026-08-24-qwen38-7797b6022c-absolute-current-main-build.json),
[TP1 preregistration](experiments/qwen38-27b-b70/notes/2026-08-24-qwen38-7797b6022c-untreated-tp1-r1-prereg.md),
and frozen wrapper passed independent audit and were committed/pushed before
one atomic untreated TP1 invocation. The fresh hardware gate and 19-file
direct/ordinary model verification passed; the exact image loaded, compiled,
became healthy, and returned the required `14` with zero cached tokens. Before
timing, the frozen broad journal pattern rejected one corrected physical-layer
`RxErr` from Samsung root-NVMe endpoint `0000:01:00.0`. No B70, model, graph,
timing, or decode-speed failure occurred, but r1 remains failed-incomplete
under its frozen rule and both strict arms are missing. The literal arm status
remains `fail-cleanup`; the repeated journal match proves that cause fired.
This closeout independently confirmed container removal, render-idle state,
cache preservation, and both evidence manifests. See the
[r1 closeout](experiments/qwen38-27b-b70/notes/2026-08-24-qwen38-7797b6022c-r1-corrected-nvme-gate-stop.md).

The repo's retained SMART/AER investigation already proves this exact event is
a stable link-side nuisance behind a healthy controller/filesystem and warns
that an `any corrected AER` gate is below the host noise floor. The 2026-08-24
unsealed read-only postmortem SMART and ext4 observations remain clean. A
separately versioned r2 classifier/packet passed three independent audits and
was committed/pushed as `eba4a9d10`. It retains every raw journal delta, uses
the same canonical reject scope in the hardware gate, parser tests, and model
arms, rejects a cursor-truncated signature fragment, and may exempt at most
one exact 21-line corrected root-NVMe block. Its fourteen-test battery passes,
and the exact r1 delta replays as one accepted block with zero rejects and an
unchanged raw hash.

The post-push prelaunch gate then resolved vLLM main to
`6648eb118d77ad001a411cf52f9c6c4719476c83`. The r2 wrapper was not invoked:
both exact roots remain absent and no hardware gate, container, model, canary,
benchmark, quality request, or GPU work ran. 7797 is now closed stale before r2
launch, not qualified or regressed. The model, graph, cache, quality,
benchmark, timing, performance floors, TP2 78-decision artifact, and accepted
TP4 152-decision overlay remain unchanged. The active action is a fresh
zero-overlay build from literal-current vLLM, exact-current XPU kernels, and
the live official nightly digest, followed by a separately named audited TP1
packet. See the
[r2 stale closeout](experiments/qwen38-27b-b70/notes/2026-08-24-qwen38-7797b6022c-r2-stale-before-launch.md).

Before building the successor, the exact stale 7797 two-image pair was added
to its USB archive and verified by compressed checksum, zstd integrity, OCI
tag/index identity, layer count, and traversal-safe tar inventory. The 9,569-
file build root was relocated with every file byte rehashed; NTFS normalized
its POSIX modes, which is disclosed rather than treated as metadata-preserving
recovery. Only the two exact recoverable 7797 image IDs were then removed.
The official base, dated stock controls, all run evidence, and accepted
decision artifacts remain; root headroom is now 21.64 GiB. See the
[storage-rotation receipt](experiments/qwen38-27b-b70/notes/2026-08-24-qwen38-7797b6022c-storage-rotation.md).

The literal-current successor build then completed normally at vLLM
`6648eb118d77ad001a411cf52f9c6c4719476c83`, XPU-kernel main
`baaa05bb4e92901219a5a072dd63f2474896f6d1`, and official nightly digest
`sha256:3ee0ec37825cc03e866a75198e6fee2a201efb68a717852ed35737a3ae59f876`.
Both the current-vLLM/stock-kernel attribution image and the both-current
zero-overlay image passed their static import, package, DSO, source-label, and
receipt gates. The external archive passes 14/14 checksums. The sole vLLM
delta from 7797 removes a duplicate `VLLM_USE_DEEP_GEMM` check in kernel
warmup; the called support function still checks the flag and XPU still
reports DeepGEMM unsupported, so no B70 behavior or speed gain is inferred.
A fresh independent check at `2026-08-24T16:59:08Z` resolved all three live
upstream identities to the exact built values. This is a freshness and static
build pass only; GPU qualification is pending. See the
[6648 build receipt](experiments/qwen38-27b-b70/data/2026-08-24-qwen38-6648eb118d-absolute-current-main-build.json).

After the build archive verified, only 7.652 GB of unused Docker builder cache
was pruned. No image, model, run evidence, compile cache, accepted decision,
or protected result was removed. Both new images remain under their exact
receipt IDs, and root headroom is about 13.44 GiB, above but close to the
unchanged 12-GiB launch floor. Recheck space and all live upstream identities
immediately before invoking a separately named, committed, audited TP1 packet.

That separately named 6648 r1 packet was launched once from clean pushed
`main`. The fresh hardware gate passed 70/70 and the both-current zero-overlay
TP1 arm passed model verification, exact canary, fresh graph compile, and
25/25 diagnostic rows. Its audited conventional median was
`30.340562433175233 tok/s`, above the historical diagnostic high, but vLLM
`main` advanced during the arm to direct successor `4f686e182a`. The
post-diagnostic freshness guard intentionally exited 5 before writing the
speed gate, strict A/B, or quality result. Close 6648 as failed-incomplete and
stale before promotion: the observation is dated evidence only, no cache or
speed is promoted, and the protected TP1 diagnostic pair and strict floor stay
`30.2178 / 30.2569` and `30.31067504052998 tok/s`. The TP2 78-decision and TP4
152-decision overlays remain intact, disabled, and unapplied. See the
[6648 r1 closeout](experiments/qwen38-27b-b70/notes/2026-08-24-qwen38-6648eb118d-r1-stale-during-diagnostic.md).

The successor is one cleanup-only vLLM commit; XPU-kernel main and the official
nightly digest did not move. That bounds the port review but does not waive the
literal-newest rebuild. The exact 6648 two-image archive and all 9,569
build-root files are now byte-verified on the USB artifact store. Only the two
recoverable stale image IDs, the duplicated ext4 build root, and unused Docker
builder cache were removed; the nightly base, stock controls, raw run evidence,
and accepted overlays remain. Final measured root headroom was 21.43 GiB. See
the [6648 storage rotation](experiments/qwen38-27b-b70/notes/2026-08-24-qwen38-6648eb118d-storage-rotation.md).

Re-resolve all three upstream identities and build the newest head next. Resume
in order TP1, TP2, TP4 without lowering a captured speed or dropping accepted
optimization work.

The live vLLM head advanced again before that build, so the intermediate
`4f686e182a` successor was not built. The atomic build instead completed at
literal-current vLLM `342b8ebd8bd4595826f29ff95dfc48679a03a95a`, unchanged
XPU-kernel `baaa05bb4e92901219a5a072dd63f2474896f6d1`, and unchanged official
nightly digest
`sha256:3ee0ec37825cc03e866a75198e6fee2a201efb68a717852ed35737a3ae59f876`.
Both zero-overlay images passed static import, package, DSO, source-label, and
14/14 external-archive gates. The cumulative two-commit vLLM delta is API
cleanup plus a CLIP/SigLIP mixed-pooling bugfix; it does not touch Qwen, XPU,
GDN, graphs, speculative decode, distributed/TP, quantization, or build inputs.
The only source-path overlap with historical work is a separate `vllm/envs.py`
hunk in the old coupled MTP patch, so it requires selective review if revived,
not wholesale application. No accepted overlay was applied or lost.

The completed build's unused Docker builder cache was pruned without removing
either new image or any evidence, restoring root headroom to about 13.53 GiB,
above the unchanged 12-GiB launch floor. This is still only a current-source
static build; TP1 qualification is pending. See the
[342b build receipt](experiments/qwen38-27b-b70/data/2026-08-24-qwen38-342b8ebd8b-absolute-current-main-build.json).

The separately named 342b r1 TP1 packet then ran once from clean pushed
`main`. Its hardware gate passed 70/70. The zero-overlay diagnostic completed
25/25 cache-zero rows at `30.337988469031558 tok/s`, above its frozen floor.
Strict replay A completed 25/25 natural-EOS rows at
`30.295550825778708 tok/s` and passed all seven exact cases, the 8/8 one-hash
repeat, the 8K needle, all 24 baseline comparisons, direct/ordinary model
verification, immutable-cache checks, and clean kernel/teardown gates. Its
speed gate missed the unchanged `30.31067504052998 tok/s` floor by only
`0.015124214751271 tok/s` (`0.049897%`).

Before replay B, an unrelated Ornith/Qwen3.6 evidence commit advanced the lab
repository's live `origin/main`. The wrapper intentionally stopped with rc 1;
replay B and an aggregate result do not exist. The engine upstream identities
did not move, and the repository commit changed neither the frozen packet nor
the running image/cache. Close r1 as failed-incomplete, not as a completed TP1
qualification or permission to lower a captured value. Its 178/178 campaign,
21/21 input, and 70/70 hardware manifests reverify; both containers are gone,
ports are free, and the 1,097-file cache stayed byte-identical. See the
[r1 closeout](experiments/qwen38-27b-b70/notes/2026-08-24-qwen38-342b8ebd8b-r1-repo-advanced-after-replay-a.md)
and original
[preregistration](experiments/qwen38-27b-b70/notes/2026-08-24-qwen38-342b8ebd8b-untreated-tp1-r1-prereg.md).

The fresh-root 342b r2 packet passed static and preservation audits, but the
final precommit freshness audit resolved vLLM `main` to its direct child
`6a9c69fa851389dcf1ee5d3a2363e27af665d26d`. R2 was therefore closed stale
before launch: its roots remain absent, ports `19773`-`19775` remain unbound,
and no hardware, model, benchmark, quality, cache, or GPU work ran. Preserve
the exact packet and wrapper as stale provenance; never invoke or relabel them.
See the [r2 closeout](experiments/qwen38-27b-b70/notes/2026-08-24-qwen38-342b8ebd8b-r2-stale-before-launch.md)
and original
[preregistration](experiments/qwen38-27b-b70/notes/2026-08-24-qwen38-342b8ebd8b-untreated-tp1-r2-prereg.md).

The successor is one direct commit adding variable-length TRT-LLM/FlashInfer
decode support for adaptive verification. It changes two FlashInfer attention
and test paths, not a Qwen- or XPU-named path or any preserved decision
payload, but it is speculative-decode-adjacent and must not be waived. Build
6a9c69f or any newer successor from literal-current vLLM, exact-current XPU
kernels, and the live nightly digest, with zero source overlay. Re-resolve all
three before and after the build.

That zero-overlay successor build resolved and built at vLLM
`6a9c69fa851389dcf1ee5d3a2363e27af665d26d`, XPU kernels
`baaa05bb4e92901219a5a072dd63f2474896f6d1`, and nightly index digest
`sha256:3ee0ec37825cc03e866a75198e6fee2a201efb68a717852ed35737a3ae59f876`.
The wheel, both immutable image exports, both full inspections, and both
no-device static preflights completed. Root ENOSPC then stopped the normal
builder while it wrote the both-current tag receipt, before the aggregate
receipt or USB archive. No GPU, model, cache compile, benchmark, or quality arm
ran. Only disposable uv, compiler, and Docker builder caches were cleared;
both new images and all optimization/result evidence remain. Root headroom was
restored above 17 GiB.

A single report-only receipt recovery then ran once from clean pushed `main`
and passed. It revalidated all three live upstream identities, both immutable
image IDs and complete label contracts, the official kernel artifact, every
original build input/log/preflight, the complete protected performance ledger,
and all 78 TP2 plus 152 TP4 decisions before and after archival. It did not
build, pull, retag, remove, expose a GPU, run a model, or create a performance
claim. The byte-identical tracked/build-root/archive receipt is
`a7b2d9a4fa1693c4ca83e98a494b249a380087963702c0f30cf558bb889400f3`;
it remains explicitly GPU-qualification-pending. See the
[recovery pass](experiments/qwen38-27b-b70/notes/2026-08-24-qwen38-6a9c69fa85-enospc-recovery-pass.md)
and [tracked receipt](experiments/qwen38-27b-b70/data/2026-08-24-qwen38-6a9c69fa85-absolute-current-main-build.json).

The fresh-root 6a9c TP1 r1 packet then ran its complete zero-overlay sequence.
The hardware gate and every non-speed gate passed. Diagnostic reached
`30.27858669748398 tok/s`, above its frozen floor. Strict natural-EOS A/B
reached `30.26782494070049 / 30.27119782672338 tok/s`. Replay A passed the
complete quality battery, and both replays passed immutable-cache gates, but
they missed the unchanged `30.31067504052998` floor by
`0.141370% / 0.130242%`. This is a completed,
repeatable speed-only miss: no protected value changes and TP2/TP4 remain
unauthorized. It permits only a separately versioned TP1 decision-compatibility
packet that maps exact relative paths and embedded `configs_hash` values into
an absent cache and compiles fresh; compiled cache transfer remains forbidden.
See the [6a9c r1 closeout](experiments/qwen38-27b-b70/notes/2026-08-24-qwen38-6a9c69fa85-tp1-r1-speed-only-miss.md)
and [structured result](experiments/qwen38-27b-b70/data/2026-08-24-qwen38-6a9c69fa85-tp1-r1-speed-only-miss.json).

The separately versioned 38-decision TP1 compatibility packet then passed its
fresh hardware gate and seeded-fresh diagnostic at
`30.268740193465128 tok/s`, above the unchanged `30.2178` floor. All 19 model
files, the exact canary, 25/25 cache-zero rows, fresh graph compilation, exact
decision bytes, cache-tree checks, kernel checks, and cleanup passed. Before
strict replay A, live lab `origin/main` advanced through an unrelated Qwen3.6
documentation/data commit. The frozen r1 rule stopped the chain with rc 1.
Neither strict replay nor the quality battery ran, so the observation is dated
diagnostic support only: the overlay remains unqualified, no protected high is
replaced, and TP2/TP4 remain unauthorized. The 161/161 campaign, 76/76 input,
and 70/70 hardware manifests reverify; the sealed cache has 497 regular files,
38 decision records, no links or special nodes, and must not be resumed. See
the [decision-overlay r1 closeout](experiments/qwen38-27b-b70/notes/2026-08-24-qwen38-6a9c69fa85-tp1-decision-overlay-r1-live-lab-stale.md)
and [structured record](experiments/qwen38-27b-b70/data/2026-08-24-qwen38-6a9c69fa85-tp1-decision-overlay-r1-live-lab-stale.json).

The remote commit did not touch Qwen3.8, the runtime, the packet, or any
protected value; vLLM, XPU-kernel, and nightly identities remained exact. At
that point this authorized preparing r2 with the immutable image and exact
decision payload, but a new hardware root, campaign root, and fresh compile
cache. Its proposed rule required the lab tree to equal live `origin/main` at
launch, then kept the local commit and frozen inputs immutable while engine
upstream and nightly identities remained hard post-arm gates. The later 0d7
freshness veto below superseded that authorization before campaign launch.

That r2 packet passed independent static and performance-preservation audits,
but the final precommit freshness check at `2026-08-24T21:44:48Z` resolved
vLLM `main` to `0d7d5ed0b2b61da53f682534f1754fe7d0251a34`. R2 was closed
stale before launch: its fresh roots remain absent, ports `19789`-`19791` are
free, and no hardware gate, model load, compile, benchmark, quality battery, or
GPU work ran. Preserve its exact preregistration and wrapper as unlaunchable
provenance; no protected speed changed. See the
[r2 stale closeout](experiments/qwen38-27b-b70/notes/2026-08-24-qwen38-6a9c69fa85-tp1-decision-overlay-r2-stale-before-launch.md).

The three-commit successor moves upstream batch-invariance code from
`model_executor/layers` to `model_executor/determinism`, adds a CUDA/FlashInfer
TP>1 speculative-decode fix that sizes the fused-allreduce/RMSNorm workspace
for the wider target or draft model, and closes an audio size-limit bypass.
The local literal-main source clone was fast-forwarded to 0d7d with no source
overlay. The general builder now requires the new determinism members at the
source, wheel, installed-package, label, import-receipt, and aggregate-receipt
stages and pins the byte-identical batch-invariance config hash. A changed or
missing upstream optimization asset therefore stops for review instead of
being silently omitted.

The literal-current 0d7d build then completed normally at vLLM
`0d7d5ed0b2b61da53f682534f1754fe7d0251a34`, XPU kernels
`baaa05bb4e92901219a5a072dd63f2474896f6d1`, and nightly digest
`sha256:3ee0ec37825cc03e866a75198e6fee2a201efb68a717852ed35737a3ae59f876`.
Both immutable zero-overlay images passed every static gate and the 14-file USB
archive battery; no GPU or model work ran. The exact
[build receipt](experiments/qwen38-27b-b70/data/2026-08-24-qwen38-0d7d5ed0b2-absolute-current-main-build.json)
remains GPU-qualification-pending. Unused builder cache was pruned after the
build. The stale 342b image pair was then exported to a verified Docker-loadable
USB archive before only those two exact local IDs were removed, restoring about
15.48 GiB free while retaining the 0d7d and 6a9 image pairs, build roots, all
run evidence, the preserved TP2 78-decision artifact, and the accepted TP4
152-decision artifact. See the
[342b storage receipt](experiments/qwen38-27b-b70/data/2026-08-24-qwen38-342b8ebd8b-storage-rotation.json).

Before launching a separately named 0d7d TP1 packet, re-resolve every live
engine identity. If still exact, run a fresh untreated cache and do not blindly
carry the old 38 decisions; compatibility must be re-derived by relative path
and embedded `configs_hash`. The TP>1 change warrants a later new-base retest
but is not evidence that the observed XPU worker-init broadcast hang is fixed;
XPU disables this fusion path.

Do not authorize TP2 until TP1 passes full qualification. Then qualify TP2
zero-overlay plus the preserved 78-decision remap, followed by TP4 zero-overlay
plus the accepted 152-decision remap.

The old/new compiled Qwen graphs and autotune candidate sets are identical,
but the nightly package version changed the compile-cache namespace and a fresh
tune selected different winners. The capped TP2 preservation test transferred
only 78 hash-matched historical `.best_config` decisions into a fresh
`a3561ef8` image compile; it did not copy compiled binaries or revert upstream.
The diagnostic arm recovered from 48.6476 to **49.0589 tok/s**, a new
overlay-identity diagnostic high, and passed its gate. The strict replay
recovered from 48.4905 to **49.0094 tok/s**, passed the
full quality battery, and left the sealed cache byte-identical, but missed the
frozen 49.0197 historical gate by 0.0103 tok/s (0.021%). Preserve it as a
quality-qualified partial recovery, not a promoted replacement. See the
[rolling qualification](experiments/qwen38-27b-b70/notes/2026-08-23-qwen38-rolling-nightly-a3561ef8-qualification.md)
and [overlay result](experiments/qwen38-27b-b70/notes/2026-08-23-qwen38-tp2-autotune-winner-overlay-result.md).

The separately preregistered TP4 winner overlay is also closed. It seeded only
152 hash-matched historical `.best_config` decisions into a fresh `a3561ef8`
image compile. Diagnostic speed reached **71.722545 tok/s**; exact-cache strict A/B
reached **71.352872 / 71.454271 tok/s**. Both strict arms cleared the frozen
historical floor and B cleared the high bar, with full replay-A quality and an
unchanged 2,117-file cache. Accept this as an exact, versioned
`a3561ef8`-plus-overlay stable profile, reported as a range with a 71.352872
lower observed replay endpoint. Do not call either endpoint independently
replicated or erase the stock 71.900199 captured high. See the
[TP4 overlay result](experiments/qwen38-27b-b70/notes/2026-08-23-qwen38-tp4-autotune-winner-overlay-result.md).
Any newer nightly requires remapping and requalification, not retention of this
older base.

The separate Qwen3.6-derived native MTP source stack remains preserved as a
patch/source research identity. It is not part of the stock target-only graph
column and must be ported selectively after the stock rolling-nightly
comparison, not discarded or applied wholesale. The default-off `mtp.fc` INT4
patch was quality-clean but rate-neutral, and the D1/D2 state audit was
diagnostic-only; neither is a mandatory performance overlay.

Use the
[rolling official-image comparison runner](experiments/qwen38-27b-b70/scripts/run-20260823-qwen38-rolling-nightly-strict-smoke.sh)
only for that comparison/replay lane. It pulls the floating tag, resolves and
launches only its immutable digest, checks the model through direct and
ordinary reads, uses a fresh ext4 cache, and retains the strict canary,
token-ID, natural-EOS, quality-baseline, and cache-replay gates. It does not
prove that literal current main was tested. The dated pinned-image runners
remain unchanged.

The frozen b2dd/1e90 zero-overlay TP4 packet now closes that dated source
stack's TP4 blank. Diagnostic measured `72.07605937552125 tok/s`; strict
natural-EOS A/B measured `71.77179128057259 / 71.82969607434323 tok/s`.
All three 25-row arms, direct/ordinary model verification, exact cache-zero
canaries, immutable-cache checks, and strict-A full quality battery passed.
After every model arm had cleaned up, the outer wrapper failed only in its
deterministic aggregation because mawk reserves `floor` as a built-in. The
original failed status remains preserved; a hash-sealed offline recovery
revalidated every gate and computed only the preregistered comparisons. Treat
the result as a qualified dated TP4 anchor with that recovery disclosure, not
as literal current-main evidence. No historical high was lowered or replaced,
no decision overlay was applied, and the higher stock strict `71.9001988117144`
capture remains distinct. See the [structured recovery](experiments/qwen38-27b-b70/data/2026-08-25-qwen38-b2dd9ce73d-tp4-zero-overlay-r1-recovery.json)
and [closeout note](experiments/qwen38-27b-b70/notes/2026-08-25-qwen38-b2dd9ce73d-tp4-zero-overlay-r1-recovery.md).

The same dated b2dd/1e90 matrix is still the active measured campaign. TP1's
nine-probe context spine, full eager-MTP0 short control, and eager-MTP2
sensitive parent passed. The expanded 25-prompt eager-MTP2 E1 then completed
with every canary, quality, acceptance, identity, cleanup, and benchmark gate
green, but matched its separate-boot MTP0 target oracle on `23/25` rather than
the frozen `25/25` requirement. It is terminally quarantined and its
`10.90171641629769 tok/s` interval median is not promotable. Both mismatches
were coherent, the quality battery was fully green, and target-only fresh
compiles are already known to vary as low as `19/25`; this cross-boot result
therefore does **not** prove MTP corruption. It fills zero exact active-context
cells. E2, the one authorized eager-MTP4 actual, is blocked and was not run.
Do not retry E1, launch E2, or open a causality detour under this campaign;
advance an independent matrix packet. The separately frozen TP2 zero-overlay
packet remains ready and must stay distinct from TP1 evidence. See the
[TP1 expansion preregistration](experiments/qwen38-27b-b70/notes/2026-08-25-qwen38-b2dd9ce73d-tp1-eager-mtp-expansion-preregistration.md),
[E1 closeout](experiments/qwen38-27b-b70/notes/2026-08-25-qwen38-b2dd9ce73d-tp1-eager-mtp2-full-r1.md),
and [TP2 preregistration](experiments/qwen38-27b-b70/notes/2026-08-25-qwen38-b2dd9ce73d-tp2-zero-overlay-r1-prereg.md).

The independent b2dd TP1 exact-depth packet then filled six real graph cells
for the same AutoRound/MTP0/F16 identity in one server: `30.0957`, `29.7669`,
`29.2778`, `28.4202`, `27.6576`, and `26.9888 tok/s` at exact active contexts
2K/4K/8K/16K/24K/32K. Every per-depth token/cache/length gate, both graph
capture markers, and the full quality battery passed. Depth zero remains
explicitly missing because an empty fixture is not an OpenAI-serving request.
These exact-context measurements are additive and do not replace or lower the
protected short-workload `30.31 tok/s` result. See the
[result note](experiments/qwen38-27b-b70/notes/2026-08-25-qwen38-b2dd9ce73d-tp1-exact-depth-r1-result.md).

The next independent b2dd packet is the TP1 target-only eager concurrency
ladder. It is preregistered but not launched: batch sizes
`1/2/4/8/16/32/64`, 128 distinct input tokens, 512 forced output tokens, two
fixed-seed repeats, and one same-engine sequential oracle for every one of the
64 prompts. Complete token arrays are retained and every batched response is
compared with its own prompt generated alone. This is raw-engine aggregate
decode evidence, not HTTP users or requests per second. A valid but
output-varying run remains experimental with its exact mismatch disclosure;
an identity, completeness, timing, or literal-quality failure is quarantined.
The two-B70 15-GiB host must not execute the full model. Graph capture and
TP2/TP4 concurrency remain separately pinned followups after the eager shape
is measured. See the
[preregistration](experiments/qwen38-27b-b70/notes/2026-08-25-qwen38-b2dd9ce73d-tp1-target-concurrency-preregistration.md).

A separate dated current-main image pair was statically certified at vLLM
`4af586e185b028acf08312a4dee381b5998a137e` and XPU kernels
`1e90ffa672ba02f17a909da11838a4c55b199783`. Both the stock-kernel control and
both-current image passed the fail-closed import/schema/ELF receipt chain and
were packaged in a checksum-tested Docker-loadable transfer bundle. No model,
GPU, benchmark, or quality request ran on this host, so this is a later
GPU-qualification-pending packet, not literal-current performance evidence and
not an inheritor of the b2dd matrix. See the
[4af build record](experiments/qwen38-27b-b70/notes/2026-08-25-qwen38-4af586e185-absolute-current-main-build.md).

## Pinned Certified Qwen3.8 TP-Scale Frontier (2026-08-23)

The certified short-decode target-only frontier uses the digest-pinned XPU
nightly image `sha256:bc979d1ba312dc8a666c57a40205f35d7fc5d96b2f7450c2c77f5b3d5243f0e0`,
AutoRound INT4 W4A16, F16 KV, one request, cache zero, and XPU Graph:

- TP1: `30.2178 / 30.2569 tok/s` conventional;
- TP2: `48.8301 / 48.9505 tok/s` conventional;
- TP4: `71.6741 / 71.5488 tok/s` conventional.

The graph column is now strict-gate qualified at every valid TP size:

- TP1: `30.3107 tok/s` natural-EOS conventional;
- TP2: `49.0197 tok/s` natural-EOS conventional;
- TP4: `71.2933 / 71.3984 tok/s` natural-EOS conventional.

Each topology has 25/25 eligible cold rows under 100-event/99-interval
accounting, cached tokens zero, full token IDs, 24/24 nonempty baseline
comparisons, seven objective canaries, an 8-run same-server repeat, and an 8K
needle. Replay cache manifests stayed unchanged. The earlier ignore-EOS rows
remain diagnostic ceilings and are not rewritten. TP4 fresh/replay full
outputs still match only 21/25, so cache sealing does not eliminate runtime
token nondeterminism; the disclosure remains mandatory. The runtime also
labels multi-GPU XPU Graph unsupported/experimental. No submission was made.
See the [strict graph-column note](experiments/qwen38-27b-b70/notes/2026-08-23-qwen38-nightly-graph-column-final-gates.md).

The bounded nightly Cartesian matrix (TP 1/2/3/4 × MTP 0/1/2/3 × graph
off/on × F16/e4m3/e5m2 KV) is now 96/96 decision-classified. Closed-by-gate
cells were not burned after a parent correctness, quality, architecture, or
expansion failure. The only strict promoted family is F16 KV, MTP off, graph
on at TP1/2/4. See the [combination closure](experiments/qwen38-27b-b70/notes/2026-08-23-qwen38-nightly-combination-closure.md).

The bounded TP1 determinism program is now closed. Exact replay of one sealed
cache matched 2/2 sensitive prompts with an unchanged cache manifest, but a
second fresh default cache diverged at token 18. Disabling Inductor max
autotune, coordinate descent, and Triton cache autotuning preserved speed
(`30.2312 / 30.2565 tok/s` conventional on two full runs) but still matched
only 19/25 complete 512-token outputs across independent fresh compiles. Do
not promote that candidate or lower the historical speed pair; keep the
cross-boot disclosure. See the [determinism screen](experiments/qwen38-27b-b70/notes/2026-08-23-qwen38-nightly-tp1-determinism-screen.md).

The old TP4 MTP2 attempt is infrastructure-invalid, not a speculative-decode
deadlock result: three workers failed concurrent compilation after shared
Triton-cache artifacts disappeared. Corrected fresh-ext4-cache smokes now boot
MTP2 at both TP2 and TP4 and pass the exact code-14/cache-zero canary. A TP4
two-prompt screen measured `31.1680 tok/s` conventional with 149/210 drafted
tokens accepted (implied 2.419/3 including target). That proves TP4 speculation
works, but misses the frozen speed and acceptance expansion gates, so no full
nightly MTP suite or deeper nightly ladder is warranted. Do not file a TP>1
deadlock report from the old root. The `71.7` row remains the fastest
target-only Qwen3.8 result for this AutoRound/nightly identity, not the lab-wide
target-only record.

The isolated-cache native dose-8 D1/D2 mechanism program is now closed. D7
stayed quality-green; D4 reproduced the exact `B70_QWEN3!!!!...` corruption.
Across all eight dose rows, every state block allocated in groups 0/1/2 was
released exactly, no block remained live, no live-slot collision occurred,
and the native GDN call observed `has_initial_state=false` at computed tokens
0 then true at 1024. The frozen verdict is that both state-slot lifecycle and
stale/missing continuation-flag mechanisms are **dead**. The isolated cache
manifest remained byte-identical and the recovered source cache was never
used as a runtime cache. The corruption is still unfixed; any next mechanism
door needs a fresh preregistration, with KV-page checksums or large
layout-adjacent canaries the highest-information next move. See the
[mechanism closure](experiments/qwen38-27b-b70/notes/2026-08-23-qwen38-chunk-corruption-d1d2-v2b-closure.md)
and the earlier
[incident/recovery note](experiments/qwen38-27b-b70/notes/2026-08-23-qwen38-chunkdiag-d7-instrumentation-incident.md).

Immediate order:

1. before every runtime campaign, resolve the literal upstream vLLM and XPU
   kernel `main` heads as well as the official rolling image. If the image
   trails either required source head, use it only as the runtime/comparison
   base and build a clearly labeled custom-current-main source identity. Remap
   accepted overlays and rerun TP1/2/4 graph sentinels before matrix work.
   Never use v0.27.1 or an older nightly as the active base;
2. preserve the pinned image, stock rolling results, accepted overlay packets,
   isolated-cache manifests, raw roots, and every captured high as distinct
   rollback/comparison identities;
3. make neural.download coverage complete before optional mechanism research:
   publish pinned, stock rolling, and rolling-plus-overlay profiles separately;
   add explicit measured/estimated/closed/quarantined/unsupported/missing cell
   states and import already-valid evidence that is absent from family pages;
4. expand the primary newest-code Qwen coverage slice across TP1/2/4 and
   context 0/2K/4K/8K/16K/24K/32K, recording decode, prefill, TTFT, VRAM,
   quality, and uncertainty rather than ranking by decode alone;
5. represent MTP4, TP3, quantization subsets, model weight revisions, KV modes,
   and runtime/overlay selectors structurally. Spend GPU time only where a real
   measurement changes guidance; use labeled versioned estimates for unknown
   lower-value gaps, and closures only where an actual architecture or frozen
   experiment gate supports them;
6. do not rerun the old pinned 96-cell Cartesian matrix unchanged. Its
   graph+MTP corruption and eager-MTP underperformance closures apply only to
   that pinned profile. For each new rolling digest, run one bounded parent
   sentinel before expanding those families; until then, label rolling cells
   missing rather than inheriting the pinned closure;
7. defer dose-8 KV-page instrumentation, upstream bug filing, the v0.27.1
   diagnostic cross-check, and other side research unless they unblock a
   high-value coverage cell or receive an explicit decision.

Evidence and correction:
[TP-scale packet](experiments/qwen38-27b-b70/data/2026-08-23-qwen38-tpscale-nightly-matrix.json),
[finding](experiments/qwen38-27b-b70/notes/2026-08-23-qwen38-tpscale-nightly-finding.md),
[audit correction](experiments/qwen38-27b-b70/notes/2026-08-23-qwen38-nightly-audit-correction.md),
and [current-main overlay preservation](experiments/qwen38-27b-b70/notes/2026-08-23-qwen38-absolute-current-main-overlay-preservation.md).

## mtp.fc INT4 integration: validated, quality-clean, rate-neutral (2026-08-22)

The default-off vLLM patch (VLLM_XPU_MTP_FC_INT4, tracked in
patches/qwen38-27b-mtp-fc-int4-b70/) was built and run on GPUs 2,3: it
boots, fail-closed loads the frozen packed buffers, passes the full
quality battery with baseline match, and runs MTP5 (acceptance 3.82).
Equal-config door A-B isolates the op effect at **-0.8% (neutral, within
noise)** - matching the operator prereg's prediction that one small
linear x5/step is sub-1% end-to-end. Verdict: NOT a standalone speed
lever; kept default-off for possible future stacking. Patch/buffers/
driver on record. See the
[cachebuild+A-B result](experiments/qwen38-27b-b70/notes/2026-08-22-qwen38-mtp-fc-int4-cachebuild-result.md).

## Active Product Track: neural.download packets

**Site follow-ups requested 2026-08-25:** see
[docs/requests/2026-08-25-site-followups.md](docs/requests/2026-08-25-site-followups.md)
— two Qwen3.6-35B reproduction guides (the family page currently has no
install route), a path-sanitizing step in the publishing flow, and a stock
(unpatched vLLM) 1..64-user sweep to pair with the tuned one. Each item
states its done-condition; the site regenerates from `guide`/`manifest`
fields, so no site-side change is needed when they land.

**Model store network share (2026-08-22):** `/mnt/usb-models/llm-models`
is exported read-only over NFS to `10.0.0.0/24`
(`ro,no_subtree_check,all_squash`; nothing else on the drive is shared —
bench-results stays private). The two-B70 host mounts it persistently at
`/mnt/lab-models` (`ro,soft,nofail`); write-refusal verified. Known
limit: this host's `eth1` links at **100 Mb/s because the link partner
(switch port or cable) only advertises 10/100** — our side now correctly
advertises up to 1000 (runtime + NetworkManager profile fixed from
`auto-negotiate: no`). Swapping the cable/switch port restores gigabit
automatically; until then remote model reads cap at ~11 MB/s.

Opened 2026-08-22. Goal: publish a variety of B70-characterized model
packages (benchmarks + patches where needed + reproducible recipes) on the
neural.download page, per the
[packet standard](docs/neural-download-packet-standard.md). First wave
(pinned + SHA-verified into `/mnt/usb-models/llm-models/`): LFM2.5 2.6B
Q8_0 (novice), Ornith 1.5 9B Q8_0 (beginner-plus), Nemotron 3.5 Lightning
30B-A3B UD-Q4_K_M (mid MoE, Intel-without-NVFP4 question), Ornith 1.5
35B-A3B Q4_K_M (enthusiast MoE optimization lane), and the
Qwen3.8-27B flagship 256K package (UD-Q4_K_XL vs UD-Q5_K_S fit-off +
mmproj-F16 vision + MTP draft, unsloth repo @ `4ca720788d1e`). Intake
finding: Ornith 1.5 is `qwen35moe` (256 experts/8 used, 41 layers, GQA
16/2, 262144 native) — supported by pinned upstream. Packet base:
upstream llama.cpp `9fee29e9435f` SYCL AOT bmg-g31 build at
`/home/steve/src/llama.cpp-neural-download-20260822`. Watchlist (not
approved): Ling 3.0 Tiny (needs BailingHybrid vLLM/XPU first), DeepSeek V4
Pro 0813 (893 GB), Qwen3.8 2.4T-A95B (4.89 TB). **All four preregistered
bring-ups passed on 2026-08-22** (1xB70, cache-zero, 128/100 diagnostic):
LFM2.5 `133.328`, Ornith 35B-A3B `105.782`, Nemotron Lightning `72.873`
(hybrid Mamba MoE confirmed running on Intel), Ornith 9B `50.109` tok/s;
flagship fit-off decided — **UD-Q5_K_S serves 262144 ctx + vision + MTP
draft on one B70 with 2.86 GiB free** (published package point
`26.668`/`26.641` tok/s MTP-assisted; Q4_K_XL alternative
`27.510`/`27.494`, +3%; vision smoke PASS). The wave is **page-ready**:
five full-schema packages registered, validator zero-error, 512-token
operating points (bands <=0.18%), 0-32K depth sweeps with SVG charts
and prefill rates, 5/5 canary batteries, and measured two-card
verdicts — one card BEATS layer-split TP2 for both A3B MoEs (Ornith 35B
-2.6%, Nemotron -3.7%), recorded as package guidance. See the
[baseline data](experiments/qwen38-27b-b70/data/2026-08-22-neural-download-firstwave-baselines.json).

Independent two-B70 audit-host raw-engine replication on 2026-08-22 closely
matched the measuring-host LFM2.5 decode curve (all depths within 0.64%). Ornith
9B stable decode points also matched, but its prefill run was contaminated by
the audit host's 15 GiB RAM + 100 Mb/s NFS paging and is not publication
evidence. Raw rows, the 13 GiB OOM negative, memory guidance, and operator
diagnostics are in
[`data/neural-download-audit-host-depth-sweeps-20260822/`](data/neural-download-audit-host-depth-sweeps-20260822/README.md).

Ornith 1.5 35B-A3B now has a lab-maintained decode patch on the pinned
llama.cpp base. It preserves the weighted expert outputs and fuses each exact
ordered seven-`ADD` reduction into one SYCL kernel, removing 240 launches per
token. Matched one-B70 tests improved raw engine decode by **4.90%** and the
fresh 12-prompt server-suite mean by **4.85%** (`99.664` to `104.499 tok/s`),
with byte-identical 400-token same-binary door-off/on output and all objective
canaries passing. A second accepted increment fuses the 30 exact recurrent
`SSM_CONV -> SILU` pairs, removing another 30 launches/token. Against the
ordered-MoE stack it improved engine decode by **1.18%** and fresh serving by
**2.10%** (`103.012` to `105.171 tok/s` mean), again with exact 400-token
door-off/on output and passing canaries. A third Qwen-derived increment fuses
80 graph-visible residual additions into the following RMSNorm/weight kernels,
bringing the stack to 350 removed launches/token. It improved matched engine
decode by **2.00%** and fresh serving by **1.37%** (`106.319` to `107.776
tok/s` mean), with exact forced output and passing canaries. A fourth transfer
from the lab's Qwen work combines each recurrent convolution-input concat with
its persistent-state copy while preserving both outputs, bringing the stack to
380 removed launches/token. It improved matched engine decode by **3.53%** and
fresh serving by **2.74%** (`105.767` to `108.662 tok/s` mean), with exact
forced output and passing canaries. A fifth, safer direct-state transfer folds
the exact one-row recurrent gather into that boundary while materializing every
graph-visible output and leaving the convolution separate. The complete stack
then removes 410 launches/token. It improved matched engine decode by **1.97%**
and fresh serving by **1.12%** (`110.646` to `111.883 tok/s` mean), again with
byte-identical forced output and passing canaries. A sixth Qwen-derived transfer
fuses each recurrent 32-element `alpha + bias -> softplus -> gate` chain while
preserving the rounded ADD tensor, bringing the stack to 440 removed
launches/token. Pooled engine decode improved **1.18%** and fresh serving
improved **2.04%** (`112.030` to `114.314 tok/s` mean); both candidate servers
beat both controls, forced output was byte-identical, and all canaries passed.
The seventh Qwen-derived transfer keeps the tuned reordered-Q4_K routed-expert
dispatcher while fusing gate, up, and SWIGLU. It removes another 120
launches/token, bringing the complete stack to 560. Mirrored engine decode
improved **2.09%** and fresh serving improved **2.33%** (`113.043` to
`115.680 tok/s` mean); all four freshness/finality gates passed, both
candidates beat both controls, forced output was byte-identical, and all
canaries passed.
An eighth Qwen-derived transfer extends the residual/RMSNorm path over the
preceding routed-plus-shared-expert ADD while preserving both graph-visible
FP32 rounding boundaries. It removes another 40 launches/token, bringing the
complete stack to 600. Mirrored engine decode improved **0.99%** and fresh
serving improved **1.41%** (`116.406` to `118.048 tok/s` mean); both
candidates beat both controls, forced output was byte-identical, and all
canaries passed.
Three later Qwen-lineage transfers complete the current source stack: recurrent
GDN RMSNorm/SiLU gating, in-place persistent GDN state I/O, and full-attention
Q/K RMSNorm-IMRoPE with direct K-cache output. Together the eleven-feature
patch removes 700 launches/token and reached a directly measured
`128.832 tok/s` fresh-server mean before runtime tuning. An independent
Ornith screen then accepted `UR_L0_V2_FORCE_DISABLE_COPY_OFFLOAD=1`: exact
output was unchanged, mirrored engine decode improved **1.26%**, and fresh
conventional serving improved **1.09%** (`126.884` to `128.273 tok/s`), with
the legacy compatibility means (`128.166` to `129.568 tok/s`) retained; 9/12
prompt-matched averages favored the candidate. The immediate-command-list
setting used by some Qwen recipes was separately rejected for Ornith serving,
so it remains unset. No context-depth points were extrapolated from the runtime
win.
The earlier wider direct-state
form remains archived as a correctness negative. The package remains a
candidate pending clean-host replay; see the [guide](repro/ornith-15-35b-a3b-q4km-b70/README.md),
[patch packet](patches/ornith-15-35b-a3b-q4km-b70/README.md), and
[MoE evidence](experiments/ornith-15-b70/notes/2026-08-22-ornith35b-moe-add-reduce-positive.md),
[recurrent-fusion evidence](experiments/ornith-15-b70/notes/2026-08-22-ornith35b-conv-silu-positive.md),
[residual-fusion evidence](experiments/ornith-15-b70/notes/2026-08-22-ornith35b-residual-rms-positive.md),
[state-fusion evidence](experiments/ornith-15-b70/notes/2026-08-22-ornith35b-concat-state-positive.md),
[direct-state evidence](experiments/ornith-15-b70/notes/2026-08-22-ornith35b-concat-state-direct-positive.md),
and [alpha-gate evidence](experiments/ornith-15-b70/notes/2026-08-22-ornith35b-alpha-gate-positive.md).
The latest routed gate/up evidence is
[here](experiments/ornith-15-b70/notes/2026-08-23-ornith35b-moe-gate-up-positive.md).
The latest MoE shared-branch residual/RMSNorm evidence is
[here](experiments/ornith-15-b70/notes/2026-08-23-ornith35b-moe-shared-residual-rms-positive.md).
The latest runtime-setting evidence is
[here](experiments/ornith-15-b70/notes/2026-08-23-ornith35b-copy-offload-positive.md).

Publication architecture is now family-first. Keep `index.html` curated;
`models/` owns compact family coverage and measured deployment pages, while
`guides.html` remains the filterable package browser. Eight family manifests
currently assign all 13 public packages exactly once. The generator fails if
a package is unassigned, multiply assigned, or mismatched with its manifest.
Qwen 27B has the deepest bounded TP/MTP/context/graph/KV map; the other seven
families expose every existing packet/profile slice plus explicit gaps without
invented estimates. Canonical family data lives in `families/*.json`, package
discovery in `packages/catalog.json`, and exact contributor metadata in each
`packages/*/package.json`. See the
[coverage-foundation note](notes/2026-08-23-neural-download-family-coverage-foundation.md).
Regenerate with `python3 -B tools/build-family-pages.py`,
`python3 -B tools/validate-repro-guides.py --write-package-catalog`, then
`python3 -B tools/build-model-pages.py`. Research-only packets can appear on a
family page at their honest maturity without entering the install catalog.

The next product work is to deepen non-Qwen combination classifications from
existing ledgers, store dated popularity/recency snapshots where available,
add typed versioned estimates with uncertainty for true gaps, and promote more
already-measured blanks before burning GPUs. Never replace a captured high
score with a projection or a different accounting convention.

## Active Optimization Lane

Qwen3.8 Flash-Next FP8 is active as of 2026-08-26. Its pinned 185.56-GB download
passed complete Git/LFS, tokenless dry-run, safetensors-header, payload-range,
and 152,089-tensor index closure. The maintained current-main XPU overlay now
constructs the model on TP4+EP4, maps the exact 11.92-GiB/rank PLE shard through
selective UVA, loads all 131 checkpoint shards on all four B70s, and completes
post-load FP8 processing at about 31.57 GiB reported per rank. Attempt 12's
explicit phase trace proved all four ranks complete the layer-0 gate, dispatch,
BF16 shared expert, and router, then fault simultaneously inside the routed
expert call before the API becomes healthy; no decode or throughput result
exists. Exact one-B70 gates pass both the real routed FP8 expert and real BF16
shared expert at the live M64 shape. The exact routed gate also passes with the
same 31.57-GiB allocation and 31.837891-GiB allocator reservation as attempt
12, so a simple allocation/reservation OOM is not established.

Attempt 13 applied the 303.125-MiB/rank embedding margin exactly but reached the
same routed boundary. Its four captures proved every dummy-profile route was
the normal padding sentinel (`id=-1`, weight zero) on every rank. The inherited
XPU alignment component did not filter that sentinel before its count/map step.
Kernel commit `2f829747503c77d4814834dffd0840fb1dd9f75a` corrects all four
alignment variants. Four focused tests, the exact all-padding M64 replay at
attempt-13 memory placement, and the ordinary valid-route real-weight M64
control all pass. The replacement stage changes only the MoE extension and the
previous stage remains intact.

Attempts 14 through 16 passed routed processing and combination through all 48
layers on all four ranks. Attempts 14 and 15 established the explicit 192-MiB
cache and block-outermost `BLHNC` layout. Attempt 16 reached cache binding and
exposed a stale QSA adapter assumption about vLLM's standardized logical cache
view. vLLM `d41e640898` now normalizes both raw and compressed QSA side caches
once at bind time, with both layout contracts covered by the passing reference
suite and no per-token work added. Attempt 17 passed cache binding/allocation
and reached final warmup, where it exposed a 29-field source versus 23-field
preserved GDN component mismatch. vLLM `687aa13dc` now selects the exact legacy
target-decode call only for that detected component and fails closed on any
speculative batch; the current 29-field path is unchanged. Attempt 18 became
the first healthy TP4 API server, with cache-clean addition/copy/JSON canaries
and deterministic repeats. Its short battery has one substantive reasoning
miss (`range(4)` squares answered `30` rather than `14`) plus one case-only
strict miss (`Yes` versus `yes`), so it is a diagnostic serving proof rather
than quality certification or speed evidence. Production head `658965050`
removes all trace/capture call sites while preserving the embedding, QSA, GDN,
and performance patches. Attempt 19 is the first instrumentation-free healthy
production baseline: both short batteries passed 5/7 strict exact cases, but
the substantive `30`/`14` miss remained and one of 16 total greedy repeats
diverged. Its three exact-identity exploratory samples measured a median
`5.221850 tok/s` after first text. This is an honest TP4/EP4/eager/MTP0/512
research cell, not a deployment or record candidate. TP1, TP2, graph,
MTP2-4, deeper context, and fresh-boot determinism remain gaps. The public
[`qwen-flash-next` family](families/qwen-flash-next.json) now accounts for the
exact FP8 child artifact and the screened matrix without inventing estimates.
See the
[bring-up ledger](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-26-xpu-overlay-preload-gates.md).

The additive 1,536-token-cap arm then passed a 987-token needle and 16/16
repeats, completed the 12-prompt cache-zero realistic suite at a preferred
`4.449168 tok/s` 99-interval median, and measured three exact-1K samples at a
`5.133588 tok/s` after-first-text median. The known 5/7 strict short-quality
boundary remains, so this closes a second research cell without authorizing
promotion. The first configured-3K arm passed an exact cache-zero 2K needle
but stopped before speed after one open-choice repeat changed between two valid
answers. That quarantine remains preserved. A repeat-v2 retry showed the old
prompt's `black`/`blue` margin was only 0.125-0.375, while prescribing the input
set produced a 9.19-10.19 margin and 32/32 first-token plus 16/16 full-output
stability. Its formal exact-2K row passed, and three comparable exact-2K samples
measured a `5.228429 tok/s` median after first text. The 2K selector is now a
research-screened cell backed by superseding evidence, with the earlier
quarantine still disclosed. The additive configured-4,352 arm then passed
exact baseline agreement, 16/16 fixed-set repeats, the exact cache-zero 4K
needle, and the formal exact-depth gate. Its formal rate was `4.456026 tok/s`;
three legacy-comparable exact-4K rows had a `5.233665 tok/s` after-first-text
median. The configured-8,448 arm then passed exact baseline agreement, 16/16
fixed-set repeats, an exact cache-zero 8K needle, and the formal p8192/o128 gate
at `3.979729 tok/s`. Two secondary rows completed at `5.170404 / 5.182353
tok/s`, but the runtime stopped during the required third row; no legacy median
or curve point is authorized. The formal 8K cell is research-screened with a
stability caveat, and helper commit `08a865143` now rejects incomplete streams.
The performance-preserving MTP1 adapter then reached a healthy TP4/EP4 API.
An audit found that the first quality arm had omitted the MTP0 baseline's
`enable_thinking=false` client setting, so its visible reasoning-text mismatch
was not valid runtime-parity evidence. The corrected unchanged-runtime arm
matched all 26 baseline comparisons, repeated one hash 16/16 times, passed the
small cache-zero needle, and measured `9.773841 / 9.372254 / 8.107468 tok/s`,
median `9.372254 tok/s` after first text with 503/505 cumulative draft tokens
accepted. This closes TP4/eager/MTP1/512 as a separate Grade-C research cell;
it does not replace the MTP0 primary result. Deeper MTP1, MTP2-4, and 16K+
wait on bounded context/cache work. The official deployment design keeps the
51B n-gram lookup table in host RAM with asynchronous row prefetch; the current
XPU lane keeps all four TP shards host-resident through selective UVA, and its
overlap behavior remains an explicit optimization audit.

The configured-512 MTP3 attempt 4 then passed its exact 20-block cache
admission, became healthy, matched all 26 bounded MTP0 comparisons, held the
fixed-set repeat to one hash for 16/16 runs, passed the small cache-zero needle,
and completed all 24 audited quality requests without cache reuse. Three
p146/o256/c1 rows returned the target hash at `17.473321 / 14.888790 /
12.538689 tok/s`, median `14.888790 tok/s` after first text. The cumulative
endpoint reported 768/768 accepted draft tokens. The inherited strict target
score remains 5/7, the needle was only 317 actual prompt tokens, and the speed
rows declined monotonically across a wide range, so this is a separate Grade-C
research cell rather than a stable ceiling, record, or 4K qualification. MTP0
remains primary and MTP1 is unchanged. The selected next deployment-shaped
gate, TP4/MTP3 at configured maximum 4,352 with a 25-block fixed cache, now
passes all 26 sealed MTP0 4K comparisons, 16/16 repeats, an exact 4,096-token
needle, and a formal exact-depth row. Three p4096/o256 rows measured
`16.578976 / 15.501565 / 14.615698 tok/s`, median `15.501565 tok/s`, with the
target hash. Median TTFT was `187.899186 s` and median wall output rate was
`1.246260 tok/s`. Compared with the separate MTP0 4K legacy screen, decode is
196.19% higher but TTFT is 52.28% slower and wall rate is 16.12% lower, so the
workload-aligned comparison is descriptive, not a causal MTP-only A/B: MTP0
used vLLM `658965050` while MTP3 used `1372c62d`. The next production work is TTFT/prefill plus fresh-boot stability rather than a
decode-only promotion. TP4/MTP2/512 now also passes all 26 MTP0 comparisons,
16/16 repeats, its bounded cache-zero needle, and three target-hash rows at
`13.586501 / 10.064085 / 11.895061 tok/s`, median `11.895061 tok/s`; its 29.61%
row span keeps it a variable Grade-C screen. The MTP4/512 arm now closes the
configured-512 MTP0-4 depth grid: all 26 MTP0
comparisons matched, repeats were 16/16, the bounded cache-zero needle passed,
and three corrected target-hash rows measured `21.119694 / 18.576249 /
20.727176 tok/s`, median `20.727176 tok/s`, with 1,716/1,716 cumulative draft
acceptance. It remains a Grade-C short screen; deeper MTP1,
graph, remaining TP1/TP2 fit, vision, full quality, and clean-host replay remain open. The
51B PLE/input-embedding shards remain
pinned in system RAM during serving; generation does not stream them from the
external checkpoint drive.

The first TP4/MTP4 exact-4K arm is now a quarantined infrastructure result,
not an open blank. Its 29-block cache admitted 4,352 tokens, but the quality
request stopped at 3,904 computed tokens when the worker-response deadline
expired during sampling. No quality JSON or timing row was promoted. Cleanup
was followed by engine resets on all four B70 addresses; all devices are
discoverable and idle afterward, but the next GPU arm must repeat the
four-rank preflight. MTP4/512 and MTP3/4K remain unchanged.

TP4/MTP2 exact-4K is also now classified, with more positive evidence but the
same deployment boundary. Its 21-block cache exposed 4,810 tokens; all 26
MTP0 comparisons, 16/16 repeats, the exact 4K needle, and the formal
p4096/o128 gate passed. The formal row measured `4.126872 tok/s` conventional
with `317.350522 s` TTFT. The first p4096/o256 row then stopped during prefill
at 3,904 computed and zero output tokens, so no comparison speed row or median
is authorized. Cleanup reset all four cards. This selector is a tested Grade-C
capability with quarantined readiness; MTP2/512 remains unchanged.

A preregistered MTP2 cache-control successor changed only the fixed pool from
21 to 32 current-source blocks. It exposed 7,329 cache tokens, passed the same
26/26 comparisons, 16/16 repeats, exact cache-zero 4K needle, and formal gate,
then completed all three p4096/o256 rows at `9.893155 / 12.078050 / 9.217264
tok/s`, median `9.893155 tok/s`. Median TTFT was `263.279224 s`, median wall
output was `0.891382 tok/s`, and cumulative acceptance was 719/748. This
establishes headroom32 as the working practical MTP2/4K selector while retaining
the 21-block quarantine as history. It does not prove causality, a speed gain,
or minimum cache; the 32-block formal row was slower than the earlier formal
row. MTP3 remains preferred.

TP4/MTP1 exact-4K now closes the remaining unclassified MTP-depth cell at the
user's practical 4K ceiling. The preregistered 32-block headroom recipe exposed
9,284 cache tokens and passed all 26 MTP0 comparisons, 16/16 repeats, the exact
4K needle, the formal p4096/o128 gate, and all three p4096/o256 rows. Those rows
measured `8.904421 / 8.868705 / 9.581812 tok/s` after first text, median
`8.904421 tok/s`; median TTFT was `232.079233 s` and median wall output was
`0.981050 tok/s`. Cumulative acceptance was 528/539. This is a separate Grade-C
support recipe, not evidence that cache headroom caused the MTP2/MTP4 boundary
and not a minimum-cache claim. MTP3 remains the preferred exact-4K recipe at
`15.501565 tok/s`, lower TTFT, and higher wall output. The TP4 eager text matrix
is therefore fully classified across MTP0-4 at configured 512 and active 4K:
MTP0/MTP1/MTP2/MTP3 are screened at 4K, while only MTP4 is explicitly
quarantined.
The 51B PLE/input-embedding state remains pinned in host RAM through UVA; the
four cards are otherwise filled to about 32.06 GiB per rank, which is the
current 128-GiB-VRAM/4K deployment policy.

The next MTP1 active-context arm is now classified without changing either
passing MTP1 result. Its configured-1,536 server passed all boot and admission
gates, then the first 1K request stopped at 768 computed prompt tokens with
zero output and reached the fixed worker-response gate. Request two was not
sent and the separate 2K boot was skipped under the preregistered stop rule.
Therefore MTP1/1K is quarantined and that combined program did not classify
MTP1/2K; MTP1/512 plus exact-4K remain unchanged. Any retry requires a
material first-request completion fix and a fresh four-rank boot. Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260828-tp4-mtp1-1536-context-attempt1-bounded-negative.json`.

The separately preregistered standalone MTP1 active-2K arm is also now
classified without changing either passing MTP1 result. Its local-NVMe
configured-3,072 server passed every boot gate and exposed 32 cache blocks /
7,561 tokens, but the first exact-2K exchange had a zero-byte completion body
and no output token recorded when the fixed 360-second client bound expired.
The subsequent engine diagnostic showed
448 computed prompt tokens and zero output, and the engine then independently
reported its own sampling timeout. Request two was not sent; no speed or
quality credit is granted. The post-failure teardown window recorded compute-
and copy-class resets on all four cards. All devices were discoverable with no
listener or residual model process afterward, but no post-reset collective was
run. MTP1/1K and 2K are quarantined; MTP1/512, exact-4K, and every captured
rate remain unchanged. Any repeat requires a material completion treatment,
new preregistration, and fresh four-rank preflight. Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260828-tp4-mtp1-3072-context-attempt2-bounded-negative.json`.

The next additive matrix cell, TP4/EP4/eager/MTP3 at active 2K, is also now
classified without changing any passing or featured result. Its local-NVMe
boot passed every identity, four-rank, placement, 25-block cache, capacity, and
health gate. Request one completed the generic exact-depth contract with 2,048
prompt and 128 output tokens, zero cached tokens, positive MTP3 counters, and a
diagnostic `5.931661 tok/s` conventional rate. It failed the separately frozen
MTP0 token-array authority beginning at generated token five, so request two
was not sent and the rate receives no speed or quality credit. This is a
bounded cross-lane parity quarantine, not isolated proof that MTP3 caused the
divergence; the MTP0 authority used a different vLLM commit and cache
allocation. MTP3/512, MTP3/exact-4K, and all captured speed rows remain
unchanged. Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260828-tp4-mtp3-3072-context-attempt1-parity-quarantine.json`.

The successor TP4/EP4/eager/MTP2 active-2K cell used the proven 32-block
headroom allocation and also completed the generic exact-depth contract, at a
diagnostic `4.526753 tok/s` conventional rate and `310.712871 s` TTFT. Its
token array diverged from the same frozen MTP0 authority at generated token 13,
so request two was not sent and no speed or quality credit is granted. This
second cross-lane result makes an MTP3-only explanation insufficient, but it
still does not isolate native MTP as the cause because the authority used a
different vLLM commit and cache allocation. MTP2/512, MTP2/exact-4K,
MTP3/active-2K, and all protected rates remain unchanged. Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260828-tp4-mtp2-3072-context-attempt1-parity-quarantine.json`.

The separately preregistered TP4/EP4/eager/MTP2 active-1K cell then passed the
fresh four-rank collective and every startup gate from the verified local-NVMe
model. Both authorized requests returned exactly 1,024 prompt and 256 output
tokens, the frozen MTP0 text hash, zero cache reuse, identical text, and perfect
85/85 acceptance at both MTP2 positions. Request one observed
`10.682699 tok/s` after first text and the repeat sentinel `12.641866 tok/s`.
The final journal artifact nevertheless retained 11 corrected records for
local NVMe `0000:01:00.0` after the frozen cutoff. No event named a B70 address,
but the preregistered clean-host rule failed, so the cell is quarantined and
both rates are diagnostic only. MTP2 configured-512, active-2K, exact-4K, and
every captured rate remain unchanged. Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260828-tp4-mtp2-1536-context-attempt1-host-quarantine.json`.

The active-8K TP4/EP4/eager/MTP2 cell is now classified as well. The verified
local-NVMe identity admitted 32 blocks / 11,264 tokens and completed its one
authorized p8192/o128 request with exact 8192/128/8320 usage, zero cache reuse,
all generic depth gates, and positive MTP2 activity: 53 drafts, 106 draft
tokens, 76 accepted, split 41/35 across positions zero/one. Its output first
diverged from the frozen MTP0 authority at zero-based generated-token index 26.
That authority used a different vLLM commit and cache allocation, so this is a
Grade-D cross-runtime parity quarantine rather than isolated proof that MTP2
caused the difference. The `6.234518 tok/s` rate and `649.717302 s` TTFT are
diagnostic only. Supervised teardown passed with all four cards idle and no
B70 event; 22 corrected storage/root-port records block clean-host/deployment
wording. MTP2 configured-512, exact-4K, MTP0 exact-8K, and every protected
speed remain unchanged. Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260828-tp4-mtp2-8448-context-attempt2-parity-quarantine.json`.

The TP4/EP4/eager/MTP1 active-8K arm is now classified without changing any
captured speed. Its verified local-NVMe boot passed the exact source/runtime,
fresh four-rank, placement, served-identity, health, and fixed 32-block
capacity gates, reporting 13,516 cache tokens and four exact 12.22-GiB
offload receipts. The sole p8192/o128 request completed in 982.7 seconds with
exact 8192/128 usage, zero cache reuse, all 25 generic gates, and active MTP1
counters (51 of 76 draft tokens accepted at position zero). Its output first
diverged from the frozen cross-runtime/cache MTP0 authority at zero-based
generated-token index 72, so the observed 4.151 tok/s and 953.3-second TTFT
are diagnostic only. The owned completed-classification path performed a
controlled shutdown and passed its cleanup gates, leaving no
listener/group/compile/RPC/temp residue and returning all four cards below
43 MiB. The intentional stop retained the known shutdown-time output-handler
notice and one shared-memory cleanup warning. No B70-addressed event occurred;
seven corrected APEI
records / seven corrected endpoint sections for local NVMe block clean-host
and deployment wording. This is a Grade-D scoped parity quarantine. MTP1
configured-512 at 9.372 tok/s, exact-4K at 8.904 tok/s, MTP0 exact-8K, and
every featured/captured rate remain unchanged. The practical TP4 eager-text
grid is now 24/25 classified (12 screened, 12 quarantined, 1 missing); only
MTP4/8K remains. Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260828-tp4-mtp1-8448-context-attempt1-parity-quarantine.json`.

The successor TP4/EP4/eager/MTP3 active-8K arm is now classified without
changing any captured speed. Its verified local-NVMe boot passed the exact
source/runtime, fresh four-rank, placement, served-identity, health, and fixed
32-block capacity gates, reporting 9,654 cache tokens and four exact
12.22-GiB offload receipts. The sole p8192/o128 request entered inference but
reached the fixed 900-second client bound without a completed response receipt
or any durably recorded output token. No usage, cache-zero, MTP-counter,
parity, TTFT, quality, or speed result exists. The owned failed-request path
drained and shut down the server, left no listener/group/compile/RPC residue,
and returned all four cards below 43 MiB. No B70-addressed event occurred; 33
corrected APEI records / 34 corrected endpoint sections for local NVMe block
clean-host and deployment wording. This is a Grade-D bounded no-receipt
quarantine. MTP3 configured-512, active-2K, exact-4K, MTP0 exact-8K, and every
featured/captured rate remain unchanged. The practical TP4 eager-text grid is
now 23/25 classified (12 screened, 11 quarantined, 2 missing); MTP1/8K and
MTP4/8K remain. Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260828-tp4-mtp3-8448-context-attempt1-bounded-negative.json`.

The next TP4/EP4/eager/MTP3 active-1K arm passed exact identity, fresh
four-rank, placement, 25-block cache, capacity, served-model, and health gates.
During request one, the server received `SIGTERM` at 00:05:06 before the
response completed. No request JSON, usage, output hash, or speed exists.
Partial server metrics retained six drafted and six accepted tokens with 1.000
acceptance at all three positions, but those counters grant no parity, speed,
quality, or deployment credit and request two was blocked. The full window had
one corrected-only NVMe receiver record and no B70 event; teardown left no
listener/process and all four cards discoverable. The active-1K cell is a
Grade-D external-signal quarantine. MTP3 configured-512, active-2K, exact-4K,
and every captured rate remain unchanged. Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260828-tp4-mtp3-1536-context-attempt1-external-stop.json`.

The final missing active-1K depth, TP4/EP4/eager/MTP4, is now also classified.
Its exact 29-block local-NVMe boot passed source/runtime identity, fresh four-
rank, placement, cache, capacity, served-model, and health gates. Both exact
p1024/o256 requests returned the frozen MTP0 text hash with zero cache reuse,
identical text, and perfect 204/204 acceptance split 51/51/51/51 across all
four MTP4 positions. Request one observed `13.326165 tok/s` after first text;
the determinism repeat observed `17.290937 tok/s`.

The exact stop sentinel then exposed a control-plane defect: it terminated the
timeout supervisor without reaching the already-detached server group. Direct
recovery produced an orderly API/engine/four-worker shutdown and final checks
found no listener or model process with all four cards idle and discoverable.
Seven corrected-only local-NVMe records independently block clean-host credit;
no B70 event appeared. The frozen teardown rule makes this a Grade-D quarantine,
so both rates remain diagnostic and no prior speed or pass is changed. Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260828-tp4-mtp4-1536-context-attempt1-teardown-quarantine.json`.

The corrected descendant-aware supervisor subsequently passed its synthetic
lifecycle test, and the separately preregistered MTP4 active-2K arm used it for
one bounded boot. Source/runtime, fresh four-rank, placement, exact 29-block
cache, capacity, served-model, and health gates all passed. Request one reached
the unchanged 360-second client bound without writing a response receipt; the
engine independently reported its own sampling timeout about five seconds
later at 384 computed prompt tokens and zero output. Request two was not sent,
and no timing, parity, MTP-counter, quality, or speed result exists.

The supervisor returned zero and final passive checks found no listener,
recorded process, compile path, or RPC path. The teardown window nevertheless
recorded compute- and copy-class resets on all four B70s plus 60 unsuccessful
fault responses. All four cards were rediscovered at low memory use, but no
post-reset collective or known-good generation canary was run. The MTP4/2K
cell is therefore a Grade-D quarantine. MTP4/512, active-1K, exact-4K, and all
captured speeds remain unchanged. No new GPU model arm may start until the
documented post-reset recovery qualification is completed. Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260828-tp4-mtp4-3072-context-attempt1-bounded-negative.json`.

The required post-reset recovery program is now complete. The first control
attempt preserved an invalid historical `eth1` interface stop; corrected
Stage A2 passed all four isolated checks and the four-rank all-reduce. Stage B
then loaded the accepted current-source TP4/EP4/eager/MTP0 identity and passed
one cache-zero exact-OK canary with normal stop and exact 17/2/19 usage. The
descendant-aware supervisor returned zero; all four worker completions, API
shutdown, process-group removal, listener removal, exact four-card rediscovery,
and idle memory passed. No B70 reset or fatal event appeared. One APEI record
did contain two corrected physical-layer sections for root NVMe
`0000:01:00.0`; this remains an explicit storage caveat rather than a hidden
clean-host claim. B70 recovery is qualified and one separately preregistered
matrix arm is authorized. The canary grants no speed, quality, or matrix credit
and the featured **71.7 tok/s** TP4 result is unchanged. Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260828-post-reset-recovery-qualification-result.json`.

A separate preregistered target-only official-quality arm now passes. On the
same TP4/EP4/eager/MTP0/current-source/4,352 identity, the non-thinking control
matched all 26 sealed MTP0 comparisons, repeated 16/16 with one hash, returned
the exact 4K needle, and kept all 24 cache observations at zero. Its corrected
semantic score is 6/7: `Yes` is correct, while the code expression still
returns `30` rather than `14`. The official Qwen thinking sampler then passed
the 4/4 scout and all 21 three-seed grid responses. Every response had
separated nonempty reasoning/final text, normal stop, complete usage, and zero
cache reuse; the code result was `14` in all four appearances. No speed row was
run or changed. The external USB disk reset once with two read errors during
the quality window, although every retained artifact reopened and hashed; the
server also retained the known forced EngineCore cleanup caveat. Therefore the
official target quality profile is screened, while MTP3 quality qualification,
fresh-boot determinism, and clean storage/deployment remain open. Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-mtp0-official-quality-attempt2-result.json`.

The preregistered MTP3 official-quality transfer attempt is now closed
inconclusive and unqualified. The verified local-NVMe boot and deterministic
Door A passed. Door B passed the 4/4 scout and 15/21 grid rows; all 19 completed
responses passed semantic, structural, usage, and cache-zero gates, with 19/19
exact final answers versus MTP0. Request 20 (`copy_phrase`, seed `2026082713`)
stopped at 98 computed and 33 output tokens, and the fixed 300-second
worker-response timeout returned API 500. No answer-quality failure or cause is
claimed. Forced post-grace cleanup produced CCS/BCS reset messages on all four
cards; final receipts show idle cards and a clear listener. The incident
kernel snapshot was clean before that forced stop. The wider window contained
corrected Samsung-NVMe receiver events, while SMART recorded zero critical
warnings, media errors, and error-log entries. No speed number or site state
changed. Any retry needs a new bounded preregistration rather than a timeout-
only change. Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-mtp3-official-quality-attempt2-result.json`.

The final practical Qwen3.8 Flash-Next cell, TP4/EP4/eager/MTP4 active-8K, is
now classified. Its corrected absolute-path attempt retained the current-source
identity and admitted 36 blocks / 9,504 cache tokens. The sole p8192/o128
request completed in 948.095 seconds with exact 8192/128/8320 usage, zero cache
reuse, all 25 generic gates, and positive MTP4 activity at all four positions:
41 drafts, 164 draft tokens, 86 accepted, split `[30,24,18,14]`. Its output
first diverged from the frozen cross-runtime/cache MTP0 authority at zero-based
generated-token index 26. The `4.025629 tok/s` rate and `918.432851 s` TTFT are
diagnostic only; this is a Grade-D scoped parity quarantine and does not isolate
MTP4 as the cause.

The completed-classification supervisor returned zero and postflight passed:
no listener, recorded group, compile path, or RPC path, four exact B70s below
43 MiB, and no B70-addressed event. The five-second shutdown grace expired
before the remaining EngineCore and workers were stopped; the known output-
handler notice and one shared-memory cleanup warning remain disclosed. Six
corrected Source-514 records named only local NVMe `0000:01:00.0`. Attempt 1 is
retained separately as a corrected, sealed pre-request command-identity stop;
it sent no model request by control-flow inference and grants no matrix credit.

The practical TP4 eager-text matrix is now **25/25 classified**: 12 screened,
13 quarantined, zero missing. MTP4 configured-512 remains
`20.72717637199404 tok/s`, MTP3 exact-4K remains
`15.50156510641242 tok/s`, and every prior captured speed is unchanged. Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260828-tp4-mtp4-8448-context-attempt2-parity-quarantine.json`.

The first deeper-context Qwen3.8 Flash-Next arm is now classified. A new
current-source TP4/EP4/eager/MTP0 identity admitted 33 blocks / 21,795 cache
tokens at max length 16,512. Attempt 1 became healthy but failed closed before
any request on a relative supervisor-path check and grants no matrix credit.
Attempt 2 changed only fresh path/ownership identity. Its sole p16384/o128
request completed all 25 generic gates with exact 16384/128/16512 usage, zero
cache reuse, a length stop, and 128 token IDs. The output-token SHA-256 is
`5706b3445c50abaaedacae0e5f52739856300701374126c23d610367c1dd1d39`.

The observed `5.219484 tok/s` and `1073.542649 s` TTFT are diagnostic only.
Semantic, repeat, and fresh-server-repeat gates were absent, so the cell is
Grade-D quarantined capability with no speed, curve, quality, deployment, or
headline credit. The completed supervisor returned zero and left no owned
residue; all cards returned below 43 MiB. Thirty-six corrected Source-514
reports / 46 RxErr log lines named only local NVMe `0000:01:00.0`, with no B70
event. The 49-entry manifest verifies at
`d1cbe2533ca024bbadf725163a0ce22cb268a54b42d83ac65cc2dd08984d1363`.

The full Flash-Next contract is now **26/480 classified**: 12 screened, 14
quarantined, and 454 missing. The completed ≤8K practical view remains exactly
25/25 and every prior speed is unchanged. Next deep-context order: MTP2/16K,
MTP1/16K, MTP4/16K, then MTP3/16K. Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260828-tp4-mtp0-16512-attempt2-generic-quarantine.json`.

The normal-MTP2 active-16K arm admitted exact 40-block / 470,712,320-byte
capacity (20,014 reported tokens), but its request stopped at 3,200 computed
prompt tokens with no output on the 300-second runtime response deadline. The
sole preregistered material treatment halved max batched/scheduled tokens from
64 to 32 while preserving that deadline and every other identity. It passed a
fresh four-rank collective, became healthy, and extended the same p16384/o128
request to 5,440 computed prompt tokens after 958.552 seconds, but still
returned no output before the same runtime deadline. This 2,240-token / 70%
extension is one bounded treatment observation, not repeat-confirmed causality
or capability.

Treatment shutdown produced eight card reset records and 58 unsuccessful card
responses across all four B70s, so supervisor/postflight rc is 70. Current
checks are residue-free and all cards are below 43 MiB. The verified 47-entry
raw manifest is
`62895c7066ae52f33e937c93c2a9b173908a1fcd03135460385ca968f41a01ba`.
MTP2/16K remains a Grade-D bounded negative with no capability, speed, curve,
quality, parity, deployment, or headline credit. The treatment tranche is
exhausted: no scheduler-16, timeout increase, MTP1 launch, or further MTP2/16K
retry is authorized in it. Any later TP4 launch requires a separately justified
lane and fresh four-rank preflight. The full contract remains **27/480**: 12
screened, 15 quarantined, and 453 missing; the ≤8K view and every prior speed
remain unchanged. Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260828-tp4-mtp2-16512-scheduler32-attempt2-runtime-timeout-quarantine.json`.

### 2026-08-28 Flash-Next coverage-contract supersession

The `27/480` total above is retained as historical campaign arithmetic but is
superseded for the public site. It incorrectly crossed all eight text-context
depths into vision, creating 240 artificial vision/context combinations, and it
mixed five legacy-runtime MTP0 screens into the latest-runtime contract. The
canonical full coverage is now **25/270 classified**: a 240-cell latest-runtime
text contract with 9 screened, 15 quarantined, 1 statically closed, and 215 missing cells, plus a
30-cell latest-runtime fixed-fixture vision contract whose cells remain missing.
The legacy MTP0 4K/8K anchors and two explicit Grade-D 24K/32K estimates are
shown separately and do not qualify latest-runtime cells. The practical 25/25
mixed-runtime campaign view remains available for historical continuity. Every
captured speed, packet result, quarantine, and protected claim is unchanged.

The user-authorized reboot then completed the fresh Flash-Next recovery chain.
Stage A3 passed source/storage identity, per-card compute, all twelve directed
peer checks, four-rank XCCL, and the bounded B70 journal rule. Stage B1 loaded
the known-good Flash-Next TP4/EP4/eager/MTP0 canary and returned exact
cache-cold `OK` with 17/2/19 usage before a clean supervised teardown; all
cards ended at 42.875--42.879 MiB. Four corrected APEI/NVMe receiver records
occurred during local-NVMe loading, including one `NonFatalErr`, but there was
no I/O error or B70 event. The recovery chain passed its frozen B70 criterion
with a continuing local-storage-link caveat. See the
[Stage B1 result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-28-post-reboot-recovery-stage-b1-result.md).

The authorized MTP0 active-16K semantic program is now closed. A3 returned one
correct fresh response and corrupted its identical same-server repeat despite
zero reported cache use. A4 then stopped the identical sole request on a
separately started server at 1,600 computed prompt tokens before first output;
cleanup recorded eight B70 engine resets and 61 unsuccessful card responses
before all four cards re-enumerated idle. This is nondeterministic long-context
runtime-stability evidence, not speed or deployment evidence. Unchanged 16K
retries and 24K/32K serving are blocked. The next admissible GPU arm requires a
fresh four-card health gate and a material runtime treatment, with the protected
short/4K identity checked before deeper context. See the
[combined A3/A4 receipt](experiments/qwen38-flash-next-fp8-b70/data/20260828-tp4-mtp0-16k-a3-a4-runtime-instability.json).

The first material runtime treatment is also closed. Stage A5 passed full
four-card recovery; A6 stopped before model load on an overlong IPC path; and
A7 changed only the optional sampling selector plus a short corrected IPC
path. Post-result source audit found that selector is inert for the frozen
`temperature=0` requests because the all-greedy branch returns before either
top-k/top-p implementation. A7 retained the known short quality boundary and exact-4K needle and
measured a diagnostic exact-4K median of `5.375813122833296 tok/s` (12.989%
above the protected `4.7578181021380175`), but the difference is unattributed
run-to-run variation rather than selector causality. It was rejected:
two byte-identical cache-zero exact-4K requests returned different 128-token
hashes. The frozen gate sent no 16K request. This is additive diagnostic
evidence only; all protected speeds and the public coverage classification are
unchanged. The next useful arm is a bounded report-only 4K trace of top-logit
IDs/values, margins, and selected greedy argmax. See the
[A7 result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-28-tp4-mtp0-sampler-native-a7-result.md).
That exact A8 trace is now source-tested and preregistered with two identical
4K requests and no deeper-context authorization; its synchronized diagnostic
rates cannot receive performance credit. See the
[A8 preregistration](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-28-tp4-mtp0-greedy-decision-trace-a8-prereg.md).
The launch subsequently closed as infrastructure-negative: the host stopped
after worker ranks 0 and 1 initialized but before ranks 2/3, checkpoint load,
health, trace output, or any request. No result or coverage changed. The trace
patch remains preserved but was removed from the active runtime at
`e5137bfd8`, restoring the changed source paths exactly to pre-trace content.
The active objective is now trace-free TP4/MTP0 at 4,352 configured tokens,
with the PLE/ngram table in host RAM and maximum safe weight residency in VRAM.
See the [A8 closeout](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-29-tp4-mtp0-greedy-trace-a8-worker-init-freeze.md).

A9 then passed every preregistered lossless and B70 lifecycle gate. The exact
51.200-GB PLE state remained host-resident, the input embedding moved to VRAM,
model load reported 31.57 GiB/card, and the 128-MiB cache exposed exactly the
predicted 4,747 tokens. The short rows were `5.466104 / 5.402373 / 5.461356`,
median **`5.461356 tok/s`** (+4.55% over the protected current-runtime anchor),
and both exact-4K rows returned the protected token authority at `5.258323 /
5.286667`, median **`5.272495 tok/s`** (+10.82%). Quality remained 6/7 with
only the inherited `30`/`14` miss, repeats were 16/16, cache reuse was zero,
and owned teardown returned four cards below 43 MiB with no B70-addressed
event. This is the preferred MTP0 placement candidate, not deployment-ready:
a fresh-server repeat remains required, and corrected local-NVMe link events
block clean-host wording. Every prior result remains protected. See the
[A9 result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-29-tp4-mtp0-4352-ple-only-a9-result.md).
The exact A10 fresh-server replica is now preregistered with no serving-selector
change. It repeats the full quality, 16/16 determinism, short, exact-4K, and
owned-teardown gates; a full pass promotes the placement to the reliable MTP0
optimization base, while any failure leaves A9 Grade C. See the
[A10 preregistration](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-29-tp4-mtp0-4352-ple-only-a10-fresh-server-prereg.md).
That replica is now closed as the required bounded reliability negative. It
repeated the exact 11.92-GiB/rank PLE placement, 31.57-GiB/card load, 4,747-token
cache, 6/7 semantic boundary, 16/16 fixed repeat, exact 4K needle, and three
protected short hashes. Its short median was a diagnostic `5.378285 tok/s`.
Both byte-identical exact-4K rows passed usage, cache-zero, length-stop, and
timing gates, but only row 1 matched the retained token authority; row 2 first
diverged at generated token 7. A9 therefore remains Grade C and is not a
reliable/lossless deployment base. No protected result changed. The next arm
uses only existing API top-score reporting on the frozen 4K request; the A8
worker trace must not be reapplied. See the
[A10 result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-29-tp4-mtp0-4352-ple-only-a10-fresh-server-negative.md).
The bounded A11 diagnostic is now frozen. It retains the exact A10 server and
prompt identity but uses the existing completion API to report the top eight
token scores for four exact-4K repeats. It changes no worker source or server
selector and cannot receive speed credit. The gate requires every selected
token to equal its reported top one, exact usage, 128 complete score rows, and
zero cache reuse. This replaces neither A9 nor the A7/A10 negative evidence;
it is designed only to locate whether the first differing greedy token already
has a different top-one ranking. See the
[A11 preregistration](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-29-tp4-mtp0-4352-ple-only-a11-api-logprob-prereg.md).
A11 passed server bring-up but closed before a diagnostic receipt because its
client incorrectly required every streaming delta to contain exactly one token
ID. The pinned API permits a delta list with multiple generated IDs and paired
logprob arrays. No four-row JSON, output hash, model inference, or speed credit
exists. Cleanup was complete and no B70 event appeared. A12 changes only that
parser contract, requires all four token/score arrays to have equal nonzero
length, validates each decision separately, and adds a focused batched-delta
test. It uses a new attempt and port with every server/request interpretation
unchanged. See the [A11 closeout](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-29-tp4-mtp0-4352-ple-only-a11-client-format-negative.md)
and [A12 retry](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-29-tp4-mtp0-4352-ple-only-a12-api-logprob-prereg.md).
A12 then completed all four exact-4K report-only rows. Every request had exact
4096/128/4224 usage, zero cached tokens, a length stop, 128 returned token IDs,
and 128 score decisions; the selected token equaled the reported top one in
all 512 decisions. Nevertheless, all four output hashes were unique, and only
one matched the retained authority. More importantly, the top-eight score
values and token ordering already differed at generated position 0, before the
first selected-token difference. At token 7 one row had an exact ID-1/ID-487
tie and selected ID 1, while the other rows preferred and selected ID 487.
This rules out a post-selection sampler substitution and locates the failure in
the repeated forward/score path. The run is mechanism evidence only and earns
no speed credit; A9 remains Grade C and all protected speeds remain unchanged.
The server first compiled six QSA kernels on the exact-4K request, so the next
bounded work is a source audit and deterministic treatment of that
long-context attention/indexing route, without claiming QSA causality before a
controlled result. See the
[A12 result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-30-tp4-mtp0-4352-ple-only-a12-logprob-mechanism-result.md).
The bounded source/XPU follow-up reproduced a concrete QSA mechanism. The
checkpoint selects 512 compressed groups: short contexts retain every visible
group, while exact 4K must choose 512 of roughly 1,024. On a tied 1x1,024
microtest, the existing XPU top-k returned 32 distinct outputs in 100 identical
launches because winner order and cutoff ties depend on local reservation
order. Stable ordering returned one and added about `4.74 us` in isolation.
Candidate vLLM commit `f68c9386f` changes only XPU QSA selection to stable
score-descending/logical-index-ascending order and passes all five focused XPU
tests. It is not promoted. A13 is frozen on a new server identity with every A10
gate unchanged; it must reproduce both retained short and exact-4K authorities
before its ordinary timing receives any credit, and a fresh-server repeat will
still be required. See the
[diagnosis and A13 preregistration](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-30-tp4-mtp0-qsa-topk-diagnosis-and-a13-prereg.md).
A13 then passed the complete frozen gate. Recovery, the inherited 6/7 semantic
boundary, 16/16 repeat, and the cache-zero exact-4K needle all held. All three
short rows retained the protected output at `5.452158 / 5.312499 / 5.380076`,
median **`5.380076 tok/s`**. More importantly, both byte-identical exact-4K
rows returned the retained authority at `5.226466 / 5.226935`, median
**`5.226701 tok/s`**, with exact usage and zero cached tokens. Teardown was
clean on all four cards and no B70-addressed event occurred. This is the first
full-model positive for the deterministic QSA treatment, but the patch remains
unpromoted and the placement remains Grade C until a separately started A14
server passes the same full battery. No protected result changed. See the
[A13 result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-30-tp4-mtp0-4352-ple-only-a13-qsa-stable-positive.md).
The exact A14 fresh-server replica is now frozen. It changes only attempt,
port, state/cache/compile/RPC, and evidence paths, while retaining the A13
source, placement, cache, prompts, authority hashes, and complete battery. A
full pass promotes the deterministic QSA treatment plus PLE-only placement to
the reliable/lossless MTP0 optimization base; any failure preserves A13 as a
bounded Grade-C positive and changes no protected result. See the
[A14 preregistration](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-30-tp4-mtp0-4352-ple-only-a14-fresh-server-prereg.md).
A14 passed preflight but the host rebooted while workers were entering
distributed initialization. It produced no checkpoint-load receipt, healthy
endpoint, client request, model output, or timing. All four cards recovered
idle after reboot; the partial evidence is preserved and its paths will not be
reused. This is an infrastructure interruption, neither a reliability pass nor
a model failure, and it changes no protected result. The exact contract must
move to a new attempt identity. See the
[A14 interruption](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-30-tp4-mtp0-4352-ple-only-a14-host-reboot-interruption.md).
The exact recovery successor is frozen as A15 on a new attempt, port, and set
of lifecycle/evidence paths. It retains every A14 model, source, placement,
cache, prompt, authority, and interpretation field. A full pass completes the
two-server reliability/losslessness contract; any failure preserves A13 and
all older results unchanged. See the
[A15 preregistration](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-30-tp4-mtp0-4352-ple-only-a15-recovery-replica-prereg.md).
A15 passed bring-up, recovery, the inherited 6/7 semantic boundary, 16/16
repeat, cache-zero exact-4K needle, and all three protected short hashes. Its
short median was `5.381340 tok/s`, essentially identical to A13. Both exact-4K
rows passed transport at `5.226537 / 5.272196 tok/s`, but returned different
non-authority hashes and first diverged at generated token 2. The stable QSA
selection treatment therefore closes a real tie-order mechanism but is not
sufficient for reliable/lossless 4K inference. It remains unpromoted; A13 is a
bounded same-server positive, A15 is the required reliability negative, and no
protected result changed. The next bounded work is diagnosis of the QSA
score/reduction path before another full model load. See the
[A15 result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-30-tp4-mtp0-4352-ple-only-a15-qsa-stable-reliability-negative.md).
A16 then captured a valid 51-record/149-digest late-prefill trace while
retaining all ordinary gates. Its first exact-4K row matched authority and the
second diverged at generated token 62, so it remained diagnostic-only. The
fresh A17 peer passed all preflights but the host stopped during four-worker
initialization, before any shard, endpoint, request, output, trace, or timing.
No OOM kill or B70 event was recorded; the prior boot did have substantial
residual swap/memory pressure and corrected local-NVMe PCIe receive events.
A17 is preserved as an infrastructure interruption. A18 is the exact fresh-
reboot trace replica on new paths and port; it changes no model or performance
selector and leaves every protected result intact. See the
[A17 interruption](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-30-tp4-mtp0-4352-ple-only-a17-host-freeze-interruption.md)
and
[A18 preregistration](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-30-tp4-mtp0-4352-ple-only-a18-post-reboot-trace-prereg.md).
A18 completed load, placement, warmup, and health, then stopped before its
first request because concurrent mainline work had changed the frozen quality-
helper hash. The change only adds an optional argument that this client does
not pass, but the no-drift gate correctly refused it. A18 is a clean pre-
request contract stop, not a model result. A19 moves to new paths/port and
freezes the reviewed current helper hash; all model and performance selectors
and the A16 trace-comparison interpretation remain exact. See the
[A18 stop](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-30-tp4-mtp0-4352-ple-only-a18-helper-hash-stop.md)
and
[A19 preregistration](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-30-tp4-mtp0-4352-ple-only-a19-current-helper-prereg.md).
A19 then repeated the host failure before shard 1. Its launch coincided exactly
with another corrected PCIe receive event from the local Samsung NVMe, which
was also the final journal event before the host rebooted. No request or model
result exists. A20 therefore changes the checkpoint/tokenizer path to the
original fully validated external intake artifact while holding the entire
runtime, placement, request, authority, and trace identity fixed. See the
[A19 interruption](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-30-tp4-mtp0-4352-ple-only-a19-nvme-correlated-reboot.md)
and
[A20 preregistration](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-30-tp4-mtp0-4352-ple-only-a20-external-model-prereg.md).
A20 stopped before model load because its supervisor ownership check still
required the former local checkpoint path. A21 corrects that report-only
contract on fresh attempt/port paths; launcher, client, and supervisor now all
bind the validated external artifact, with no inference selector change. See
the
[A20 stop](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-30-tp4-mtp0-4352-ple-only-a20-supervisor-path-stop.md)
and
[A21 preregistration](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-30-tp4-mtp0-4352-ple-only-a21-external-model-prereg.md).
A21 then loaded all 131 shards of the exact validated external checkpoint on
all four ranks, became healthy, completed the full frozen battery, and tore
down cleanly. Its journal classifier found no blocking event, although one
corrected local-Samsung-NVMe PCIe RxErr/NonFatalErr occurred during the
successful external load. A19's reset was a confirmed uncorrected data-fabric
event and the NVMe remains the leading correlated suspect, not a proven sole
cause. A17/A19 were also each the second full load in a boot after severe
memory/swap pressure, whereas A21 was the next boot's first; storage and
second-load pressure remain confounded. Use the external artifact and at most
one full load per fresh boot until separated safely. Recovery, the inherited
6/7 semantic boundary, 16/16 repeatability, exact 4K needle, all three short
authority hashes, and both cache-zero exact-4K authority rows passed. The
report-only trace timings receive no performance credit and no protected result
changed. During A21's first external load, physical free memory fell to about
1.03 GiB and essentially all 8 GiB of swap was occupied while about 47.8 GiB
remained reclaimable/available. The observed SSH/UI stall therefore has direct
host-pressure evidence: external reads overlapped heavy reclaim/swap-out and
high-latency local-NVMe swap writes. No OOM, hung-task event, runtime failure,
or new reset occurred, and the host recovered after teardown. A16/A21 match through model
input and all layer-0 outputs, then first
differ at `layer_1_output`; zero-based layer 1 is the sole PLE-bearing decoder
layer. This localizes the next trace to that layer invocation but does not yet
prove whether PLE lookup/addition or the layer's later operations differ. See
the
[A21 result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-30-tp4-mtp0-4352-ple-only-a21-external-trace-result.md).
Fixed-input isolation then closed the active FP8-byte TP4 reduction, a pinned-
host selective-UVA lookup with the real PLE output geometry, 64 sequential
short-convolution chunks plus dirty valid-slot reset, and 4K n-gram context
progression. Each returned exact repeatability/oracle agreement. The first
short-conv harness used reserved null slot 0 and is explicitly invalid; the
corrected slot-1 gate passed. No arithmetic or protected result changed. See the
[PLE isolation](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-30-ple-fixed-input-isolation.md).
A22 passed every pre-endpoint gate and produced all four exact PLE placement
receipts, then failed closed while loading because patch 0023 finalized shard
coverage after the first of two valid child-prefix deliveries. Shards 126/127
are present; a sibling weight separates them from 0-125. No endpoint, request,
trace, quality, or performance evidence exists, no host/GPU fault occurred, and
all protected results remain unchanged. Source
`f69a0ef46338f93636671c87caa527b3ac2ca129` moves validation to the root stream,
accepts the real 126+2 grouping, and passes 25 focused tests. A23 is frozen on
new paths/port with the exact A22 inference identity, an explicit all-rank trace
receipt, and an atomic one-load boot claim. The A22 boot is consumed; A23 needs
another explicit reboot and becomes the first trace-pair member only if it emits
the trace. See the
[A22 result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-30-tp4-mtp0-4352-ple-only-a22-loader-stream-boundary-negative.md)
and
[A23 preregistration](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-30-tp4-mtp0-4352-ple-only-a23-root-stream-trace-prereg.md).
A 2026-08-30 verified storage reclaim then removed three older local model
copies, preserved their USB-backed compatibility paths, and increased internal
free space from 94 GiB to 231 GiB without changing the active Flash-Next
checkpoint. Because the external load took about 583 seconds versus roughly
71--80 seconds locally, A24 returns only the checkpoint path to the verified
local tree on new attempt/port/lifecycle paths. The user explicitly authorized
this bounded retry in the recovered A22 boot; hard gates require at least
120000000 KiB available memory, 8000000 KiB free swap, and 220000000000 free
NVMe bytes before the one-shot claim. All inference, tracing, quality, and
performance selectors remain A23-exact. See the
[A24 preregistration](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-30-tp4-mtp0-4352-ple-only-a24-local-inner-trace-prereg.md).
Its first supervisor invocation stopped before the launch wrapper because the
generated wrapper/client names omitted the new `-local` suffix. No attempt
marker, model read, run directory, or GPU process existed. Those two references
and dependent hashes were corrected before retry; inference identity is exact.
A24 then loaded all 131 local shards in about 84.38 seconds, became healthy,
and completed the full battery without a host freeze or GPU fault. The inherited
6/7 semantic boundary, 16/16 repeat, 4K needle, and three protected short hashes
passed; short median was 5.515783 tok/s. Both exact-4K rows were same-server
stable at 5.394570 / 5.347805 tok/s but shared the same non-authority hash, so
the client failed closed and nothing was promoted. The rank-0 inner trace has
64 records and 171 tensor digests; despite requested rank mode `all`, no rank
1--3 files appeared, so no all-rank receipt is claimed. A matching fresh-start
rank-0 trace is required to identify the first internal PLE difference. Five
NVMe PCIe events occurred during the otherwise successful local load/warmup;
there was no reset, OOM, or reboot. Do not perform another local load in this
boot. See the
[A24 result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-30-tp4-mtp0-4352-ple-only-a24-local-inner-trace-result.md).
A25 is the flattened fresh-start control for A24's rank-0 inner PLE trace. It
must be the first and only Flash-Next full load after a separately authorized
reboot, then compare exactly 64 records and 171 tensor tuples against A24.
Its vLLM head is `ca20c4465ca34fc733aac70416b75d7cb8a1c46f`; the four
post-A24 changes are inactive process-offload placeholder, liveness, filtered
loading, and ordinary-loader isolation paths, while A25 retains the UVA path
and every inference selector. An independent audit caught and removed
unconditional selected-name bookkeeping from the ordinary iterator before
this re-freeze. The wrappers validate in about one second, reject this already-
used boot, and preserve all protected results. See
the
[A25 preregistration](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-30-tp4-mtp0-4352-ple-only-a25-fresh-inner-trace-prereg.md).
A25 produced the required well-formed fresh trace but is lifecycle-negative:
the launch wrapper's source-only mode unexpectedly executed the derived server
without the frozen supervisor. The frozen client correctly refused that
endpoint. A diagnostic client that removed only supervisor admission retained
all server identity, request, trace, quality, hash, and assertion gates, so the
result is useful for localization but cannot be promoted. The inherited 6/7
semantic boundary, repeat suite, 4K needle, and all three short hashes passed;
short median was `5.419691 tok/s`. The two exact-4K rows completed at
`5.312945 / 5.273093 tok/s` with distinct non-authority hashes and failed
closed. A24/A25 each contain 64 records and 171 tensors. Their first 23 tensors
match; the first difference is zero-based layer 1's GatedDeltaNet
`attn_out`, after the complete PLE lookup/dequant/projection/gate/convolution,
PLE addition, and attention hyperconnection inputs match exactly. PLE is not
the first fresh-start divergence. Reliability diagnosis now moves inside the
layer-1 GDN path while async-UVA PLE remains a valid speed candidate. The
server tore down cleanly; all protected results are unchanged. See the
[A25 result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-30-tp4-mtp0-4352-ple-only-a25-fresh-inner-trace-result.md).
The separate XPU PLE process-offload candidate is now source-safe enough for a
later bounded A/B: GPU-placeholder coverage is correct, host waits have a
terminal failure signal and finite deadline, and index-first loading selects
exactly 132 PLE entries in 33/131 checkpoint files before materialization. The
focused gates passed, but no process-offload model launch or speed claim exists
yet; A25 must run first. The initial XPU transport is synchronous and is a
correctness candidate, not the finished official asynchronous-overlap design.
See the
[process-offload hardening note](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-30-ple-process-offload-prelaunch-hardening.md).
The hardware-aligned speed path is now clearer. Qwen specifies that the 51B
table remain in host memory with its sparse row lookup asynchronously
prefetched. Draft upstream vLLM PR 54371 implements the closest current pattern
for CUDA: pinned UVA, a dedicated side stream, persistent output, and layer-1
lookup started before layer 0. The B70 port will preserve the proven XPU UVA
lookup and TP4 reduction, add a separate default-off XPU side-stream selector,
and leave synchronous UVA as the control. The broad draft is not being
cherry-picked, and the blocking process worker is now a fallback comparison.
A25 remains first. See the
[async-UVA alignment plan](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-30-async-uva-ple-alignment-plan.md).
The default-off XPU async-UVA candidate is now implemented at vLLM
`d14396e27247c1b251da0ce24a0942772c4b002f` and preserved as patch 0031.
It starts the sole raw FP8 PLE lookup before layer 0 on a dedicated XPU stream,
joins at the layer-1 boundary, and retains the exact main-stream int8 TP
reduction and all later arithmetic. The actual-source TP4 gate cycled
`64 -> 1 -> 42 -> 2` tokens for 100 repetitions per rank; every async result
matched the synchronous embedding bytes and every generation retained one
cross-rank hash. Failure cleanup, selector guards, non-FP8 masking, and
default-off scheduling were independently reviewed and tested. This is an
exact component pass, not a speed result; one trace-off full endpoint load and
the complete short/4K gate are next. The protected `5.515783 tok/s` target-only
and approximately `20.727 tok/s` MTP4 results remain unchanged. See the
[component result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-30-tp4-async-uva-ple-component-pass.md).
A26 is the frozen trace-off endpoint arm on attempt 26/port 19698. Its client
verifies the live server environment contains the async selector and retains
the complete semantic, repeat, short, exact-4K needle, cached-zero, and
authority-hash gates. The current A25 boot is already consumed, so the guarded
A26 launch is the first and only full Flash-Next load after the next reboot.
See the
[A26 preregistration](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-30-tp4-mtp0-a26-async-uva-endpoint-prereg.md).
A26 completed as a bounded endpoint negative. Recovery, the inherited 6/7
semantic boundary, 16/16 short repeat, exact-4K needle, and both cache-zero
transport gates passed. The short median was `5.395973 tok/s`, 2.17% below the
protected `5.515783 tok/s`. Exact-4K measured `5.276427 / 5.192318 tok/s` with
`114.453 / 108.876`-second TTFT, but the rows produced different non-authority
hashes. The async selector is not promoted and no speed receives credit. Clean
teardown restored all four cards and host memory; protected target-only and
MTP4 results remain unchanged. See the
[A26 result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-30-tp4-mtp0-a26-async-uva-endpoint-negative.md).
A27 was preregistered to restore synchronous PLE and change only the M4 MoE
config entry from four to eight warps. Its launcher and client proved that the
tracked config file was loaded, but they did not prove which batch-size key was
selected. Later A28 traces and source review show production decode enters the
routed kernel at M1; the unchanged key `1` therefore remained active and the
intended key `4` treatment was inert. See the
[A27 preregistration](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-30-tp4-mtp0-a27-moe-warps8-endpoint-prereg.md).
A27 completed as a bounded endpoint reliability negative with an inert speed
treatment. The config-file load receipt, recovery, accepted 6/7 semantics,
16/16 repeat, needle, and cache-zero transport checks passed. Short decode
measured
`5.561458 / 5.473329 / 5.501703 tok/s`, median `5.501703`, or 0.255% below the
protected frontier. Exact-4K row 1 matched authority, but row 2 did not. The
run neither tests nor rejects the M4 component gain at the endpoint; it instead
exposes an insufficient selection receipt. Nothing is promoted. Teardown was
clean; protected results remain unchanged. See the
[A27 result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-30-tp4-mtp0-a27-moe-warps8-endpoint-negative.md).
The exact-shape layer-1 GatedDeltaNet history replay then passed two independent
qualification processes: 100 full 4K trajectories and 6,400 native calls per
process, with identical canonical digests at all 64 chunks and no mismatch.
This is a bounded synthetic negative, not a production reliability clearance;
it weakens basic native recurrent-kernel nondeterminism and moves the next
reliability discriminator to production QKVZ/BA and state-slot/cache capture.
See the
[GDN history result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-30-gdn-history-replay-qualification.md).
A28 is now frozen as a report-only full target-step profile on synchronous PLE
and the default MoE configuration. It captures four pure decode contexts after
the exact 4K fixture's 64 chunked-prefill iterations, discards the first for
analysis, and aggregates three across all four ranks. Its timing is permanently
ineligible for speed credit. A28 must be the next boot's only full model load;
the profile will choose the next optimization rather than spending another
boot on a sub-noise component projection. See the
[A28 preregistration](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-30-tp4-mtp0-a28-target-step-profile-prereg.md).
A28 captured four valid rank traces and four rank tables, but its frozen
offline analyzer failed closed before the ordinary quality/speed battery due
to a timestamp-unit contract defect. The raw capture was recovered without a
rerun by normalizing absolute-nanosecond XPU submission anchors with Kineto's
`baseTimeNanoseconds`; all four ranks then expose exactly 5,586 device events
in each captured context. The p4096/o128 request passed generic depth and cache
gates but returned the known A10-row-2 non-authority hash, so A28 has no speed,
quality, reliability, or promotion credit. The valid profile identifies 97
BF16 allreduces per token with severe rank-arrival asymmetry; the production
decode MoE path (M1 routed-kernel input, ~26.08 ms across rank means) and dense
projections are the largest concrete noncollective buckets, while
GDN, QSA, and PLE are not primary speed targets.
The raw dense cross-rank mean was `10.0314 ms`, but an offline stability audit
localized that inflation to one rank-3 cycle where four unrelated layer-7 GEMMs
slowed together. The other 11 rank-cycles form a tight `7.5745 ms` mean /
`7.5795 ms` median; use about `7.58 ms/token` as the steady dense baseline.
Next, analyze the already captured collective ordinal/layer arrival timeline
offline before selecting another endpoint arm.
Protected results remain unchanged. See the
[A28 result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-30-tp4-mtp0-a28-target-step-profile-result.md).
That offline timeline is complete. Every cycle has 97 BF16 `[1,2560]`
allreduces (5,120 bytes), just above the pinned oneCCL 4,096-byte low-latency
threshold. The normalized submission-arrival proxy is most often latest on
ranks 2 and 3 and reaches 16.362 ms, but it is not wire latency. The next
bounded no-model test compares the exact shape at thresholds 4,096 and 8,192,
with exact hashes and protocol receipts. See the
[A28 collective timeline](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-30-tp4-mtp0-a28-collective-timeline.md).
That six-process A/B passed exact hashes and protocol receipts. Raising the
threshold selected `Rt64_PCIE` and reduced p95/p99, but combined median improved
only 1.13% (`91.522` to `90.490 us`), below the frozen 5% gate. It is preserved
as lossless component neutral and does not justify an endpoint load. Next,
screen the actual production M1 real-weight MoE shape. See the
[threshold result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-30-tp4-bf16-allreduce-ll-threshold-neutral.md).
That M1 screen is a lossless component positive. Across three real-weight
default/candidate/default brackets, changing only `num_warps` from 4 to 8
reduced median latency by 9.27%, 9.20%, and 8.46%, with one exact hash per seed
across 300 candidate/control repeats. A separate tuned-folder run proved key
M1 and effective warps 8 were selected. A fresh endpoint arm must use that
effective-key receipt and the full quality/reliability battery; A27's
file-load-only receipt is forbidden. See the
[M1 component result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-30-moe-m1-warps8-component-positive.md).
The bounded stage-3 refinement retained exact bytes but was neutral: seed
changes were -0.72%, +1.14%, and -1.88% versus stage-4 brackets, with 0/3
clearing the frozen 3% gate. Keep eight warps and four stages; stop the
stage-depth sweep. See the
[stage-3 result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-30-moe-m1-warps8-stage3-neutral.md).
A29 is the frozen endpoint candidate for the qualified M1 map. It derives the
last synchronous full-battery path at isolated attempt 29/port 19701, preserves
every quality and protected-hash gate, and adds an official-resolver receipt
for requested M1, selected key 1, and effective warps 8. It rejects the old M4
folder, async PLE, tracing/profiling, MTP, and source drift. Static validation
and independent review pass. The current boot is consumed; A29 is prepared but
will not reboot or launch without a later explicit decision. See the
[A29 preregistration](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-30-tp4-mtp0-a29-moe-m1-warps8-endpoint-prereg.md).
Before launch, a second audit caught that the active kernel workspace had
advanced by one preserved default-off commit while the loaded stage remained
sealed at its older source. A29 is refrozen with those identities separated;
all source/stage checks now pass before the boot marker, and the workspace is
checked again immediately before service. The treatment and protected results
do not change.
The 512-expert top-k path also had an unused FP32 scoring workspace. A
default-off treatment removed it with exact outputs and 7.19--9.12% lower
synchronized component latency across three fresh-process brackets. At 48
calls/token this projects to only about 0.143 ms/token, far below endpoint
noise, so it does not displace A29 or justify another model load by itself. See
the [component result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-30-topk-512-workspace-component-positive.md).
The next bounded dense-path screen uses the existing Xe2 BF16 grouped-GEMM
implementation on real layer-0/layer-47 attention HyperConnection weights. A
component-only `_xpu_C` and matched grouped library are sealed in an isolated
stage; preparing that stage exposed and fixed three latent local source/build
contract mismatches, preserved as patch `0007`. The frozen one-B70 test is
control/candidate/control, requires exact consumed bytes, and cannot authorize
an endpoint claim. It performs no reboot, server launch, or full checkpoint
load. See the
[HC M1 preregistration](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-30-hc-m1-grouped-gemm-prereg.md).
The first layer-0/down control passed, but its grouped candidate failed closed
before timing: the Xe2 interface requires `N % 32 == 0`, and the initial 324
real outputs were padded only to 336. That attempt has no performance credit
and its raw evidence is preserved. The exact successor pads with 28 zero rows
to `N=352`, adds a preflight alignment guard, retains comparison of only the
324 production-consumed outputs, and uses a new evidence root. See the
[N336 result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-hc-m1-grouped-gemm-n336-preflight-negative.md)
and [N352 preregistration](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-hc-m1-grouped-gemm-n352-prereg.md).
The corrected four-pair screen completed with exact consumed bytes and zero
discarded outputs in every repeat. Down was neutral at -0.59% / +2.45% for
layers 0/47. Up was 65.12% faster at layer 0 and passed all gates; layer 47 was
74.34% directionally faster but failed attribution because control drift was
23.72%. Two fresh up-only brackets per sampled layer are frozen next; a pass
authorizes only a 48-layer round-robin component screen. See the
[four-pair result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-hc-m1-grouped-gemm-four-pair-result.md)
and [repeat preregistration](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-hc-m1-grouped-gemm-up-repeat-prereg.md).
Both fresh up-only repeats retained exact output and every grouped candidate
was 62.76--70.10% faster. Repeat 1 passed both layer gates; repeat 2 failed the
frozen family gate because its linear controls drifted 5.26% / 7.04%, above
3%. The 48-layer screen is therefore not yet authorized. Next use a separately
frozen same-process alternating discriminator to remove process-to-process
control drift without weakening the output or speed gates. See the
[repeat result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-hc-m1-grouped-gemm-up-repeat-result.md).
The follow-up discriminator is frozen as two fresh same-process alternating
runs per sampled layer. Each run uses 31 paired cycles with reversed order on
alternate cycles, requires exact full outputs, at least 50% median and 20%
minimum per-cycle reduction, and no more than 10 points of order bias. All four
must pass before the 48-layer screen is allowed. See the
[alternating preregistration](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-hc-m1-grouped-gemm-up-alternating-prereg.md).
The hardened alternating gate passed in all four distinct processes. Median
paired reductions were 68.54--69.94%; every cycle improved at least 63.83%,
order bias stayed below 0.35 points, and every full BF16 output matched the
pre-candidate production authority. The independent aggregate now authorizes
the real-weight round-robin component screen, but not integration or
an endpoint claim. See the
[alternating result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-hc-m1-grouped-gemm-up-alternating-result.md).
Source and A28 profile review corrected that screen from 48 attention weights
to all 97 MTP0 target up projections: attention and MLP HyperConnection weights
for 48 layers plus the final mixer. The two-process production-order screen
passed exact output and performance gates. Full-bank medians fell from
`3.256665 / 3.326745 ms` to `1.579440 / 1.545463 ms`, saving
`1.675420 / 1.779963 ms` or `51.45 / 53.49%`; the worst cycle still improved
`50.09%`. This authorizes only an opt-in source-integration candidate. The
component's duplicate 1.271 GB layout is endpoint-ineligible; integration must
replace or release the original 635.7 MB bank and still pass a full endpoint
A/B. See the
[97-weight result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-hc-m1-grouped-gemm-round-robin-result.md).
The guarded single-storage source integration is now preserved as vLLM commit
`8c247a52f` and patch `0032`. It is default-off, exact-97/TP4/PP1/MTP0/eager
only, binds the existing selective PLE-only UVA contract, preserves the
logical parameter and loader through a shared packed allocation, and passed
the official layerwise reload cycle. M1 grouped execution is exact and uses a
fresh returned output. A focused XPU test also proved that the ordinary
packed-view linear fallback is not byte-exact at M2, so every non-M1 input
currently fails closed and the treatment is endpoint-ineligible. The frozen
S1 discriminator now tests one real weight at M2 and M64 through contiguous
authority, packed-view linear, packed matmul, and grouped E=1 in eight isolated
one-card arms. It performs no reboot or full-model load and cannot authorize a
source or endpoint claim. See the
[S1 preregistration](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-hc-up-mgt1-packed-fallback-s1-prereg.md).
S1 attempt 1 failed safely before Torch/XPU import because its worker inherited
`/usr/bin/python3`, which lacks `safetensors`; the receipt and empty arm set are
preserved as an orchestration negative. Attempt 2 binds the exact `vllm-xpu`
interpreter and prefix, verifies the dependency, and moves to a new no-clobber
evidence root without changing any provider or interpretation rule. See the
[attempt-1 result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-hc-up-mgt1-packed-fallback-s1-a1-preflight-negative.md)
and
[attempt-2 preregistration](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-hc-up-mgt1-packed-fallback-s1-a2-prereg.md).
S1 attempt 2 then passed twice: all 16 arms were finite, repeatable, and
byte-exact across contiguous authority, packed-view linear, packed matmul, and
grouped E=1 at M2/M64. Grouped was directionally fastest, reducing the fixed-
order descriptive medians by `60.64 / 60.82%` at M2 and `46.84 / 42.53%` at
M64. This authorizes only the S2 correctness expansion across five real
weights and M2--4096; no source, endpoint, or speed claim is promoted. See the
[S1 result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-hc-up-mgt1-packed-fallback-s1-result.md)
and
[S2 preregistration](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-hc-up-mgt1-packed-fallback-s2-prereg.md).
S2 completed all 120 arms with clean evidence closure. Grouped E=1 was
byte-exact in all 30 real-weight/M cells. Packed-view linear and packed matmul
were each exact in only 22/30, sharing eight mismatches at M2/M8, so neither
is a universal low-M fallback. Grouped was directionally faster through M64,
slower at M256/M1024, and neutral at M4096 under the descriptive fixed order.
Because the frozen S2 rule required unqualified exactness, the original
all-provider S3 is not authorized. The prospective replacement is a newly
frozen 194-arm S3g census of authority versus grouped across all 97 M64
weights; it remains nonlaunchable until its distinct tool plan, hashes, and
independent review are complete. See the
[S2 result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-hc-up-mgt1-packed-fallback-s2-result.md)
and
[S3g intent](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-hc-up-mgt1-grouped-s3g-intent.md).
The distinct S3g tooling is now implemented and frozen: all 97 M64 weights,
authority then grouped only, 194 isolated arms, a new no-clobber evidence
root, and unchanged historical smoke/S1/S2/S3 plan identities. The worker
rejects excluded providers before evidence or device work. Independent review
passed the exact frozen hashes and fail-closed contract, so S3g is launchable;
a complete pass can authorize only a separate source-dispatch design. See the
[S3g preregistration](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-hc-up-mgt1-grouped-s3g-prereg.md).
S3g then passed all 194 arms: grouped E=1 was byte-exact to authority for all
97 real M64 HC-up weights, with finite/repeatable output and complete evidence
closure. Grouped was descriptively faster on 97/97 weights; cross-weight
medians were `21.588938` versus `37.978688 us`, and the median per-weight
reduction was `42.822%`. These remain fixed-order component timings. The pass
authorizes only a separately guarded default-off dynamic-M source-dispatch
design and focused tests, not a rebuild, endpoint, or claim. See the
[S3g result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-hc-up-mgt1-grouped-s3g-result.md).
The remaining production-shape gate is now designed as S4g: authority versus
grouped on the five real sentinels at every integer M1--64, 320 cells and 640
isolated arms. The accompanying default-off source design binds the actual
one-sequence/64-token scheduler, uses an immutable 65-entry XPU rows table,
keeps one packed weight bank and fresh outputs, and forbids mutable per-call
state. Neither packet permits a build or endpoint. See the
[S4g preregistration](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-hc-up-grouped-s4g-all-production-m-prereg.md)
and
[dynamic-M source preregistration](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-hc-up-grouped-dynamic-m-source-prereg.md).
Independent static review passed S4g as launchable. It also tightened the later
source guard to require the scheduled-token override remain unset, making the
effective scheduler cap exactly 64 before any weight treatment; this does not
change the frozen S4g component run.
S4g passed all 640 arms: grouped was byte-exact in all 320 five-sentinel/M1--64
cells, with complete row/input/weight and evidence closure. Together with the
all-97 M1/M64 passes, production component correctness is closed. The
default-off dynamic-M source candidate then passed 5/5 focused tests against
the real staged operation and 25/25 Qwen configuration tests, including native
all-M, two-stream, official reload/post-reload, and malformed-state coverage.
It is preserved as vLLM `797769b34` and patch `0033`. A first 3-pass/2-fail
test invocation is retained as an invalid-harness negative (fake-oracle and
extension-preload errors, no runtime failure). No build, endpoint, or claim is
yet authorized. See the
[S4g result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-hc-up-grouped-s4g-result.md)
and
[source result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-hc-up-grouped-dynamic-m-source-result.md).
The component-only grouped stage cannot serve Flash-Next because its extension
was intentionally built without GDN. A separate full-serving A1 build is now
frozen: it retains the accepted 18-file stage, rebuilds `_xpu_C` with both GDN
and grouped/MoE at clean kernel head `eeee7d6`, and replaces exactly the matched
extension, GDN library, and grouped library in a new local-NVMe stage. It
performs no reboot or full model load and must pass a separate loader/schema,
HC, GDN, MoE, and collective qualification before any composite A30 endpoint
arm is frozen. See the
[full-stage preregistration](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-hc-grouped-full-serving-stage-a1-prereg.md).
A1 completed all 711 native build steps with both captured exit codes zero,
then failed closed before stage assembly because its first post-build CMake
path assertion described the user-local tool rather than the activated vLLM
venv. The later oneDNN cache-type mismatch was reconstructed from the frozen
driver and exact cache; A1's outer failure text was not separately captured.
Preserve A1 as a procedural negative, not a kernel failure. The assembly-only
A2 successor consumed the exact hash-bound A1 outputs without recompiling and
produced a closed 18-file candidate: all 15 untreated files match the accepted
stage, and the matched `_xpu_C`/GDN/grouped trio resolves candidate-locally with
`$ORIGIN`. A2's runtime-manifest SHA-256 is `a4e83ec3...`; its finalizer
evidence is `2c049273...`. The separate A2 qualification is now frozen and
independently reviewed: validation-only and 5/5 CPU contract tests pass. It
must next pass accepted/candidate schema parity, 5/5 HC and 25/25 config tests,
two fresh retained GDN-history qualifications, the exact real-weight M1 MoE
gate, and TP4 collective repeatability. It performs no server or full model
load; a pass authorizes only freezing composite A30. The current boot remains
unconsumed by a full model load and no reboot is required. See the
[A1 result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-hc-grouped-full-serving-stage-a1-result.md),
[A2 finalizer result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-hc-grouped-full-serving-stage-a2-finalizer-result.md),
and [A2 qualification preregistration](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-hc-grouped-full-serving-stage-a2-qualification-prereg.md).
The first A2 qualification invocation stopped before evidence or device work:
the normal no-render-owner path returned the final false comparison from its
shell loop, and `set -e` exited silently. This is a supervisor-only procedural
negative; the candidate stage remains byte-exact and statically valid. A3 is
frozen as the exact successor, adding only an explicit successful return and a
fresh evidence path while retaining every device test and interpretation. See
the [A2 procedural result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-hc-grouped-full-serving-stage-a2-qualification-procedural-negative.md)
and [A3 preregistration](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-hc-grouped-full-serving-stage-a3-qualification-prereg.md).
A3 reached its first runtime import gate and exposed a second harness error:
the accepted native extension was required to expose/map the grouped operator
that only the candidate adds. No tensor test or model load ran. Direct clean
imports show the actual pinned contract is stronger and coherent: all 32
accepted schemas are preserved byte-for-byte, none is removed, and the
candidate adds exactly 14 frozen schemas from its four-commit kernel chain.
A4 is frozen with that exact additive-schema gate, the retained A3 shell fix,
and a fresh evidence path; every device, retained-output, and promotion boundary
is otherwise unchanged. See the
[A3 schema result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-hc-grouped-full-serving-stage-a3-schema-contract-negative.md)
and [A4 preregistration](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-hc-grouped-full-serving-stage-a4-qualification-prereg.md).
A4 passed the full stage qualification in about 130 seconds. It preserved all
32 accepted schemas with zero removals and exactly 14 pinned additions, passed
5/5 grouped-HC and 25/25 Qwen config tests, reproduced two exact 6,400-call GDN
history arms, retained the exact M1 real-weight hash across 100 repeats, and
passed four-card health plus 100 identical TP4 BF16 reductions. Postflight card,
loader, stage, journal, and render-owner closure also passed. The external
evidence-manifest SHA-256 is `ca218488...`. This authorizes freezing A30 only;
no full model, endpoint speed, quality, or promotion claim exists yet. See the
[A4 result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-hc-grouped-full-serving-stage-a4-qualification-positive.md).
A30 is now frozen as the composite endpoint candidate on attempt 30/port
19702. It derives from A29's complete M1 eight-warp battery, adds only the
qualified grouped-HC selector and full-serving stage identities, and binds the
live server environment, exact source chain, manifests, and A4 evidence before
inference. The postflight rejects any new internal-NVMe event during the run.
Six static contract tests and all generated-source/validation-only
checks pass without consuming the boot marker. A quality/speed pass remains
candidate-only: matched same-stage flag-off control and a fresh flag-on repeat
are required for attribution. The current boot followed an unexplained
overnight unclean reset with no model process active; its mounts, memory, swap,
and source state are healthy, so no additional reboot is required. See the
[A30 preregistration](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-tp4-mtp0-a30-hc-grouped-m1-endpoint-prereg.md).
A30 then completed as a bounded endpoint negative. Recovery, the accepted 6/7
semantic boundary, the 4K needle, all 16 repeats, and all three protected short
hashes passed, but short decode was only `5.416309 / 5.415455 / 5.403828`
tok/s (median `5.415455`), 1.82% below the protected result. The two cache-zero
exact-4K rows ran at `5.229220 / 5.044012 tok/s` but returned different
non-authority hashes, first diverging from authority at generated-token indices
18 and 2. Two corrected internal-NVMe receive events during shard loading also
tripped the conservative postflight gate; there was no I/O, OOM, GPU, or
teardown failure. The composite does not justify matched control/repeat loads.
Keep grouped HC default-off and preserve `5.515783` MTP0 and approximately
`20.727` MTP4 unchanged. See the
[A30 result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-tp4-mtp0-a30-hc-grouped-m1-endpoint-negative.md).
The next no-full-load screen tested native TP4 MoE without expert parallelism.
With exact layer-0 checkpoint weights and the real four-rank 5,120-byte BF16
XCCL reduction, EP4's critical median was `529.431 us`; tuned no-EP TP4 reached
`484.110 us`, an `8.560%` component improvement. That is below the conservative
15% screen, and the layouts differed in 2,436/2,560 reduced BF16 elements.
No-EP's observed net allocation projects about 105.375 MiB/card at 48 layers,
dominated by 105.469 MiB of extra refined-scale metadata and net of EP's small
expert map. Do not spend a full-model load on this layout. The gate tooling and
negative result are preserved in the
[EP4/no-EP component result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-tp4-mtp0-ep4-vs-noep-component-negative.md).
A four-rotation real-layer EP4 Latin square then mapped every 128-expert
partition onto every physical B70. Partition medians were `409.794-413.915 us`
and device medians `411.290-414.428 us`, but independent review correctly
classified its single `446.734-us` partition-1/device-1 cell as an unresolved
interaction rather than a transient outlier. A frozen four-cycle matched
replicate then measured penalties of `-2.075 / -5.532 / +0.881 / +0.442%`,
zero above its 5% gate, with exact partition hashes. Static rank/device
reordering is now closed without an endpoint load. See the
[partition/device result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-tp4-mtp0-ep4-partition-device-latin-square-negative.md).
Those build-only commits advanced the clean kernel workspace from `359466a` to
`eeee7d6`; the sealed serving stage and all protected results are unchanged,
but A29's workspace-source guard is now intentionally stale. Refreeze and
re-audit that guard against the exact four-commit chain before any future A29
endpoint load.
An exact-shape one-B70 MoE screen also found a lossless M4 component win,
but A28 later proved M4 is not the current single-sequence endpoint shape:
raising only `num_warps` from 4 to 8 reduced real-weight balanced-EP4 median
latency by 20.2--21.1% on two hidden seeds while retaining exact bytes for
100/100 repeats on each. The tuned-folder selection check passed. The seemingly
faster `BLOCK_SIZE_K=64` family changed bytes on the second seed and is rejected
from lossless promotion. The M4 result remains a valid component measurement,
but the production decode kernel uses M1; re-screen M1 before any endpoint arm.
See the
[M4 MoE component result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-30-moe-m4-warps8-component-positive.md).
A four-rank synthetic dispatch/combine collective screen also passed exact rank-order,
reduce-scatter, and 100-repeat hash gates. Across three process starts, reusing
buffers and reducing directly into the final output lowered the slowest-rank
median from `748.464` to `722.777 us/layer`, a 3.43% component reduction or
about 1.23 ms per 48-layer cycle. A28 later proved that production decode does
not use this per-layer all-gather/reduce-scatter shape, so the endpoint
projection is withdrawn and no runtime arm should use it. See the
[TP4 collective screen](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-30-tp4-moe-collective-cycle-component-screen.md).

The prior Qwen3.8 27B matrix and DeepSeek 0731 REAP GPU qualification are
paused, not abandoned. The 0731 artifact itself passed its complete pinned
storage gate on 2026-08-28 at
`data/model-intake/post-download-validation-20260826/20260828T201005Z/summary.json`;
its revision-bound three-stage DSpark pack also passed construction and is
indexed by
`experiments/deepseek-v4-flash-reap-xpu-b70/data/2026-08-28-deepseek-v4-flash-0731-dspark-draft-pack.json`.
Its fail-closed target qualification driver and separate 256-token smoke / 2K
full launch arms now pass CPU-side contract tests; see the
[prelaunch gate note](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-08-28-deepseek-v4-flash-0731-prelaunch-gate-readiness.md).
No DeepSeek GPU launch occurred. Its pre-reboot memory blocker is historical:
the user rebooted and the Flash-Next recovery chain passed. DeepSeek remains
paused because Flash-Next coverage is the active priority.
No historical speed or quality result transfers to either artifact. Their
accepted results, patches, and launch identities remain protected. Accepted
Qwen3.8 27B GGUF target-only results were measured on the
two-ASRock-B70 reference host. Its AutoRound INT4 TP2 work used a selected pair
from the four-B70, 125-GiB host; the two-B70, 15-GiB host remains a source/op-
audit worker and must not run the full server. DFlash, MTP, prompt reuse, and
other speculation remain separate result classes and outside target-only
headlines.

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

The independent exact-depth HTTP packet then qualified this same Q4_K_M TP2
identity at exact 2K/4K/8K/16K/24K/32K active prompt tokens. Decode measured
`49.4895 / 49.0103 / 48.3004 / 47.0306 / 45.5346 / 44.4373 tok/s`; TTFT
measured `1.945 / 3.860 / 7.862 / 16.300 / 25.347 / 35.059 s`. Every row
returned 128 token IDs, was cache-zero, and passed the exact-length/context
gate. This is additive grade-C repeated-token shape evidence, not natural
prose, and contains no interpolation or inherited TP1 point. See the
[result](experiments/qwen38-27b-b70/notes/2026-08-25-qwen38-q4km-tp2-http-depth-r1-result.md).

The subsequent TP2 HTTP concurrency R2 passed twice on fresh 64-slot servers.
At 1/2/4/8/16/32/64 users, median aggregate decode measured
`42.6942 / 61.8847 / 87.5664 / 108.3716 / 109.1466 / 127.4998 / 165.3873
tok/s`. Every response returned all 128 raw token IDs with cache reuse off;
there were no cross-base oracle collisions, and the worst pointwise relative
range was `1.717%`. Greedy text is batch-shape-dependent, so this qualifies
output isolation and service capacity rather than sequential byte identity.
The pilot rates remain excluded and no point is interpolated. See the
[R2 result](experiments/qwen38-27b-b70/notes/2026-08-25-qwen38-q4km-tp2-http-concurrency-r2-result.md).

On 2026-08-30, a default-off exact F16 `ffn_down` cache qualified a higher c64
endpoint on the same two-B70 Q4_K_M target-only lane. Same-binary controls
centered at `160.981046 tok/s`; two fresh candidates measured `168.344562` and
`167.933317 tok/s`, for **`168.138940 tok/s`** (`+4.45%`). Both candidates
matched the preregistered fixed 64-request batch oracle 64/64, all cached-token
counts were zero, and no output collision or kernel error occurred. The cache
costs about 6.5 GiB/device and did not improve single-user MMVQ decode, so the
single-user headline is unchanged. See the [qualified result](experiments/qwen38-27b-b70/notes/2026-08-30-qwen38-q4km-tp2-exact-f16-cache-c64-result.md).

The follow-on comma-list build then composed exact `ffn_down` and `ffn_gate`
caches. Two fresh candidates measured `175.798577` and `175.449010 tok/s`,
for a new **`175.623794 tok/s`** c64 center. Both matched the same frozen batch
oracle 64/64 with cache zero, no output collision, clean shutdown, and no
kernel errors. This is `+4.45%` over the one-family record and `+9.10%` over
the matched cache-off controls. The tradeoff rises to approximately 13
GiB/device; exact peak VRAM remains open, and the result does not change the
one-user headline. See the [pair result](experiments/qwen38-27b-b70/notes/2026-08-30-qwen38-q4km-tp2-exact-f16-cache-pair-c64-result.md).

The same exact two-family cache then qualified a near-capacity c96 endpoint.
Two fresh candidates measured `192.350949` and `192.332958 tok/s`, for
**`192.341954 tok/s`** with `0.0094%` range and 96/96 complete same-shape
control-batch oracle identity in both attempts. The requested 32K pool became
an effective 49,152-token pool (96x512), and peak used VRAM was about
30.48/30.35 GiB per card. The separate isolated sequential comparison was
50/96, so this qualifies candidate-vs-control identity and aggregate capacity,
not batch-invariant text. See the [c96 result](experiments/qwen38-27b-b70/notes/2026-08-30-qwen38-q4km-tp2-exact-f16-cache-c96-result.md).

A follow-on default-off c96 activation-conversion dedup passed 96/96 exactness
twice but is performance-neutral. Feature-on centered at `192.850545 tok/s`;
identical-backend feature-off controls centered slightly higher at
`192.867941 tok/s`. The apparent `+0.0906%` cross-binary delta was smaller than
known Intel AOT relink variation and is not claimed. Active source and backend
were restored to the r26 identities. See the [R27/R28 result](experiments/qwen38-27b-b70/notes/2026-08-30-qwen38-q4km-tp2-c96-f16-act-dedup-r27-result.md).

The 2026-08-15 Q4_K fusion passed a clean build, mechanism counter, same-binary
control, and complete 12-prompt cold suite. It improved the conventional
median by `+1.701%`; all complete output hashes remained exact. The Q8_0 TP2
transfer separately reached `36.772932 tok/s` conventional with 12/12 matched
complete outputs. On 2026-08-16, Q8 and Q4_K_M also passed exact, arithmetic,
JSON, factual, logic, Python-result, repeat-stability, and 3,829-token needle
canaries. Q8 is the primary quality-conservative service identity; Q4_K_M is
the explicitly lower-precision speed lane.

The exact Q8_0/F16-KV packaged TP2 launcher now has its own strict headline.
Two fresh full-suite servers measured `36.733956` and `36.718938 tok/s`; the
paired class-balanced median is **`36.726447 tok/s`**. Both attempts passed the
12-prompt/six-class, 512-cap, cache-zero workload and objective canaries, and
their complete token arrays matched 12/12. The outputs also match all 12
historical raw-completions response hashes. This closes the package-headline
gap without transferring authority to chat-template, TP1, MTP, long-context,
or concurrency workloads. See the [strict result](experiments/qwen38-27b-b70/notes/2026-08-27-qwen38-q8-tp2-strict-reasoningoff-native-r2-result.md).

The one-B70 Q8_0/F16-KV package also qualified independently at
**`19.619240 tok/s`** from fresh-server values `19.600348` and `19.638132`.
Both complete varied suites and objective batteries passed with cache zero,
and TP1 token arrays matched 12/12 across servers. TP1 differs from the TP2
raw oracle 12/12 (first divergent tokens 59-444), so it is disclosed as a
separate deterministic arithmetic identity. The exact same TP1 binary's prior
7/7 expected-answer, 8/8 repeat, 7,617-token needle, and 16/16 cache-zero gates
provide the broader quality binding. See the [TP1 strict result](experiments/qwen38-27b-b70/notes/2026-08-27-qwen38-q8-tp1-strict-reasoningoff-native-r1-result.md).

An archived contributed one-B70 GPTQ INT4 route was validated on 2026-08-16. Native
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

The separately preregistered 33,024-token one-slot service profile then passed
all six exact 2K/4K/8K/16K/24K/32K cells. Decode measured `21.835160 / 21.673278
/ 21.270146 / 20.927452 / 20.650133 / 20.389854 tok/s`; TTFT measured `1.385 /
2.606 / 5.192 / 10.533 / 16.139 / 21.873 s`. Every receipt was cache-zero and
returned 128 token IDs. The repeated-token fixture is grade-C shape evidence,
not natural prose, and the disclosed prompt-throughput proxy includes HTTP
scheduling and first-token work. This closes the exact 32K/decode/TTFT gap for
the official-FP8 TP2 tuple.

The first output-audited HTTP concurrency profile established a four-slot
control at `81.086716 tok/s` for c4. A preregistered capacity screen then found
that active service slots—not model compute—were the limit. The p32
confirmation reached `470.181647 tok/s`, and the first p64 confirmation reached
`695.792088 tok/s`. Enabling direct oneCCL P2P access then passed the frozen
five-percent promotion gate and was confirmed on two wholly new servers:
c1/c2/c4/c8/c16/c32/c64 measured `21.557059 / 41.424196 / 81.299381 /
157.990884 / 293.363030 / 504.387101 / 774.394144 tok/s`. All are active-slot
points; c64 median/p95 TTFT is `0.769 / 1.526 s`. Every response returned 128
raw token IDs with cache zero and passed output isolation. This closes the
current c1-c64 short-context concurrency gap for the exact official-FP8
TP2/MTP0/direct-P2P tuple without interpolation or extrapolation.

The default-off block-W8A16 dispatch then raised this official-FP8 lane to
`35.011369 tok/s` for one fresh cache-zero MTP0 response, `31.489587 tok/s` at
the directly measured 32K point, and `1,112.570323 tok/s` conditioned median
at c128. Publisher MTP depth 1 first used a separate legacy 256-token service identity: it
measured `61.699580 tok/s` for one user and peaked at `1,091.642460 tok/s`
median at c64, with 7/7 sequential cases, 8/8 repeat stability, and 512/512
concurrent semantic cases passing. Its original service had no 32K result;
the later strict deterministic profile closes that gap below. MTP0 remains
3.32% faster at its separate c128 optimum. The concurrent MTP1 service requires XPU
kernels `1e90ffa672`, whose upstream mixed speculative/non-speculative GDN
correction replaced an older kernel that aborted at c16.

The bounded MTP2 one-layer-reuse screen is closed as a split research result:
single-user decode rose to `83.646518 tok/s`, but c64 aggregate fell to
`737.190110 tok/s`; MBT768 regressed further to `712.790232` and MBT1024 did
not run by the frozen stop rule. It is not native two-layer MTP or a candidate
default. See the
[result](experiments/qwen38-27b-b70/notes/2026-08-26-qwen38-fp8-block-w8a16-mtp2-reuse-result.md).

The exact draft local-argmax follow-up is also closed negative. It matched the
MTP2 sequential control exactly, retained `82.823927 tok/s` for one user, but
regressed c64 to `673.064810 tok/s` and missed the frozen 875 tok/s gate. No
collective sub-variant or replication ran. See the
[result](experiments/qwen38-27b-b70/notes/2026-08-26-qwen38-fp8-w8a16-mtp2-local-argmax-r1-result.md).

The built-in dynamic MTP2/MTP0 schedule is closed negative as well. Its exact
`[(1,1,2), (2,128,0)]` policy retained `83.336453 tok/s` and exact static-MTP2
quality for one user, but the separately declared, output-audited c64 batch
reached only `641.328344 tok/s`. That misses the 875 tok/s gate and regresses
versus the same-shape static MTP0, MTP1, and MTP2 controls. No replication or
threshold sweep ran. See the
[result](experiments/qwen38-27b-b70/notes/2026-08-26-qwen38-fp8-w8a16-mtp2-dynamic-r1-result.md).

The active-width GDN repair plus active-lookahead Mamba-state allocation
enabled useful dynamic-MTP mechanism and aggregate-capacity research. However,
the MTP2–MTP9 singleton ladder used a selected 40-prompt-token high-acceptance
fixture. Its `146.814418 tok/s` MTP8 point is diagnostic only and must not be a
package headline or public graph endpoint.

The subsequent varied 12-prompt repeat measured `58.537756` and `58.244309
tok/s`, with unique prompts and `cached_tokens=0`, but it requested only 128
output tokens. The promotion policy required the fixed 512-token natural-
completion cap. An audit on 2026-08-27 therefore removed the `58.391033 tok/s`
center from public/package headlines and marked LocalMaxxing
`cmtb5n45n0021qq01n13vly2h` for recommended withdrawal. The raw runs remain
screening evidence. The harness now fails closed: short or filtered runs cannot
emit `realistic_final_gate.passed=true`, and payload builders re-derive
eligibility from raw rows rather than trusting that boolean. See the
[audit correction](experiments/qwen38-27b-b70/notes/2026-08-27-qwen38-fp8-w8a16-mtp8-realistic-cold-result.md).

The compliant replacement matrix then completed. Two fresh-server attempts per
profile measured W8A16 MTP0 at `34.772270`/`34.740755 tok/s`, MTP1 at
`55.760069`/`55.782147 tok/s`, and dynamic MTP8 at
`68.049727`/`62.432362 tok/s` under the full 12-prompt, six-class, 512-cap,
cache-zero contract. All workload and objective-canary gates passed, but every
pair matched only `8/12` complete token arrays. Byte-identical compiled-cache
replay (`10/12`), graph-off eager (`10/12`), and graph-off/W8A16-off eager
(`8/12`) controls also failed. Compiled-cache identity, XPU Graph, and the lab
W8A16 dispatch were therefore each not required for that instability. Those
original matrix rows remain rejected.

The later deterministic GDN-state and explicit oneCCL-completion treatments
qualified compiled MTP0 at `34.031596 tok/s`. The packed-two-row Gemma RMSNorm
replay plus deterministic Inductor then qualified static MTP1 at
**`51.918757 tok/s`** from two fresh empty-cache attempts (`51.606902` and
`52.230611`). Both passed the full 12-prompt/six-class, natural-512-cap,
cache-zero workload and canary gates; all 12 complete token arrays matched
across repeats and both qualified MTP0 target attempts. Dynamic MTP remains
withheld.

That exact deterministic MTP1 profile subsequently passed a preregistered
2K/4K/8K/16K/24K/32K exact-depth sweep. All six cache-zero 128-token arrays
matched the qualified MTP0 depth oracle; the directly measured 32K point is
**`46.636241 tok/s`** with `10.487 s` HTTP TTFT. This is Grade-C
repeated-token shape evidence, not a natural-prompt headline or LocalMaxxing
result. The first 2K request's one-time draft-kernel JIT is disclosed and its
observed value was retained rather than replaced.

Dynamic MTP8 remains rejected after the bounded R34-R38b exactness campaign.
The full strict R34 attempt matched only 7/12 qualified target arrays. Serial
native GDN made rebuilt static MTP1 exact but left dynamic MTP8 divergent at
token 128; serial packed block-FP8 moved that sentinel's first divergence to
token 441. Global batch invariance was byte-identical to that result, while
progressive serial FlashAttention, with and without its redundant causal mask,
returned the first divergence to token 128. Every sentinel was cache zero and
the required mechanism markers fired. None supplies a public speed. The
qualified user-facing FP8 speculation profile therefore remains static MTP1,
not the empty/withdrawn dynamic row. See the
[structured closeout](experiments/qwen38-27b-b70/data/2026-08-28-qwen38-fp8-dynamic-exactness-r34-r38b-summary.json).

A subsequent one-B70 TP1 eager/default-dispatch control measured
`11.405360`/`11.413057 tok/s`; every workload and canary gate passed, but the
fresh servers again matched only `8/12` complete outputs. Divergences began at
token 6. TP2 and cross-rank oneCCL are not required, so a P2P-off TP2 screen is
not justified as the next determinism test. The unresolved surface is inside
the one-rank official-FP8 target/runtime path.

The same integrity audit removed strict featured headlines from six other
package identities without deleting their measurements: LFM2.5 2.6B, Ornith
1.5 9B, and Nemotron 3.5 cite raw operating-point/canary artifacts that are not
closed in this repository; Ornith 1.5 35B natural-response hashes matched 0/12
across fresh stock servers; Qwen3.8 Q8 TP1 had only a raw-engine tg128 rate;
and Qwen3.8 Q8 TP2 had only a mismatched historical reasoning-policy capture.
The later two-server TP1 and TP2 campaigns above have now closed both Q8 gaps.
The other affected
packages remain **strict headline pending** while their honestly scoped curves
and historical evidence remain available. See the full
[benchmark integrity audit](docs/benchmark-integrity-audit-20260827.md).

The next singleton step, MTP9, reached `158.602110 tok/s` but retained only
`889.607586 tok/s` at c64, below the frozen aggregate-retention gate. A 64-slot
treatment fell to `806.950345`; two busy-period latch treatments reached only
`61.620428` and `157.939541` on the diagnostic fixture with `866.085639` c64 for the corrected
variant; and keeping MTP8 through c2 reached `146.822210` on that fixture but only
`836.139048` at c64. These are measured negatives. No dynamic-MTP single-user
policy is promoted until the corrected 512-cap varied suite and independent
quality/determinism gates pass twice.

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
- [archived contributed GPTQ/MTP route and lab status](community/sergiiob-qwen38-27b-vllm-xpu/STATUS.md)
- [one-B70 GPTQ target-only graph validation](community/sergiiob-qwen38-27b-vllm-xpu/validation/2026-08-16-local-target-only-graph-validation.md)
- [one-B70 GPTQ native-MTP matrix](community/sergiiob-qwen38-27b-vllm-xpu/validation/2026-08-16-local-mtp-matrix-validation.md)
- [GPTQ quality/KV/runtime-dtype decision](community/sergiiob-qwen38-27b-vllm-xpu/validation/2026-08-16-quality-kv-dtype-decision.md)
- [official FP8 vLLM/XPU TP2 reproduction](repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/README.md)
- [official FP8 graph result](experiments/qwen38-27b-b70/notes/2026-08-16-official-fp8-vllm-graph-tp2.md)
- [official FP8 direct-P2P c64 result](experiments/qwen38-27b-b70/notes/2026-08-26-qwen38-fp8-tp2-http-p64-p2p1-confirmation-r10-result.md)
- [official FP8 block-W8A16 MTP0 result](experiments/qwen38-27b-b70/notes/2026-08-26-qwen38-fp8-block-w8a16-tp2-p128-result.md)
- [official FP8 block-W8A16 MTP1 result](experiments/qwen38-27b-b70/notes/2026-08-26-qwen38-fp8-block-w8a16-mtp1-tp2-result.md)
- [official FP8 deterministic MTP1 strict result](experiments/qwen38-27b-b70/notes/2026-08-28-qwen38-fp8-mtp1-deterministic-r32-result.md)
- [official FP8 deterministic MTP1 exact-depth result](experiments/qwen38-27b-b70/notes/2026-08-28-qwen38-fp8-w8a16-mtp1-exact-depth-r33-result.md)
- [official FP8 strict 512-cap matrix result](experiments/qwen38-27b-b70/notes/2026-08-27-qwen38-fp8-strict-profile-matrix-result.md)
- [official FP8 TP1 strict target-control result](experiments/qwen38-27b-b70/notes/2026-08-27-qwen38-fp8-tp1-strict-target-control-result.md)
- [official FP8 dynamic MTP2/MTP0 negative result](experiments/qwen38-27b-b70/notes/2026-08-26-qwen38-fp8-w8a16-mtp2-dynamic-r1-result.md)
- [official FP8 dynamic MTP8 replication](experiments/qwen38-27b-b70/notes/2026-08-27-qwen38-fp8-w8a16-dynamic-mtp8-r16-replication-result.md)
- [official FP8 dynamic MTP9 negative](experiments/qwen38-27b-b70/notes/2026-08-27-qwen38-fp8-w8a16-dynamic-mtp9-r17-negative.md)
- [official FP8 MTP8-through-c2 negative](experiments/qwen38-27b-b70/notes/2026-08-27-qwen38-fp8-w8a16-dynamic-mtp8-c2-r21-negative.md)

Do not retry the built-in TP2 SYCL profiler or the unsafe root-both remote-write
prototype inherited from Qwen3.6 work. Both caused device faults/resets. Do not
overlap BMG AOT compilation, a model workload, or a large download on this
15 GiB host.

## Active Research: Qwen3.8 27B Q4_K_M target-only TP1

Opened 2026-08-21 on the four-B70 measuring host after its second xe
recovery: single-B70 no-speculation decode from the exact promoted TP2
source stack (both restore patches hash-verified, byte-identical model),
oneAPI 2026.0.0 BMG-G31 AOT build, accepted runtime-door set, GPU 0. The
registered baseline is **`26.047863` / `26.068073 tok/s`** conventional
median over two fresh-server cold suites with **12/12 identical complete
output hashes across restarts** and `cached_tokens=0` on all 24 requests.
This is a new one-GPU identity: TP2-oracle equality is 0/12 by legitimate
reduction-order difference, and the full quality battery is still required
before any promotion. Goal: 30+ tok/s per GPU without weight, KV, or
quality changes. Two levers are landed, both bit-exact against the
registered oracle with mechanism counters at 48 per decode graph:
widening the GDN state-I/O matcher to the full-model 48-head shape
(`27.358865`/`27.351846 tok/s`, `+5.03%`/`+5.01%`) and widening the conv
state-I/O + SILU-L2 matcher/kernel to the 10240-channel width
(`27.707324`/`27.712055 tok/s`, cumulative `+6.37%`/`+6.39%`). The third
lever landed the QK-norm-RoPE fusion after widening two remaining
RMS-input shape pins (`27.843898`/`27.863806 tok/s`, cumulative
`+6.90%`/`+6.97%`, `fused_qk_norm_rope=94240` per leg, 24/24 hashes
exact). Every previously shape-blocked accepted fusion now engages at
TP1. The full quality battery then passed (seven exact canaries, 8/8
repeats, long-context needle, `pass_all=true`) and the final-binary
official capture is **`27.813629`/`27.824790 tok/s`** with 24/24
oracle-exact hashes: quality-validated at `+6.8-7.0%` over the day-open
baseline, and approved by LocalMaxxing as
[`cmt9m8i0b00z3li01o1ragvte`](https://www.localmaxxing.com/runs/cmt9m8i0b00z3li01o1ragvte)
after the 1-GPU category and provenance review. Under the 2026-08-27
class-balanced aggregation rule, final-J's current headline is
**`27.825726 tok/s`**; `27.824790` remains the secondary all-prompt median.
The cold-weight GEMV diagnostic
then closed the z-row question: the m=6144 kernel is healthy standalone
(536.7 GB/s cold vs 381.7 in-graph), and the in-graph tax is
per-activation quantize + dispatch gap (~25 us inside each 62 us
window; the bench's shared activation is memo-deduped, in-graph's 48
distinct activations are not). The remaining 27.8->30 pool (~2-3
ms/token) is therefore runtime-level (second-queue overlap or
command-list batching), not shape widening; producer-side Q8 emission
stays rejected for exactness. See the
[z-row verdict](experiments/qwen38-27b-b70/notes/2026-08-22-qwen38-q4km-tp1-zrow-cold-verdict.md).

- [lane registration](experiments/qwen38-27b-b70/notes/2026-08-21-qwen38-q4km-tp1-lane-open.md)
- [baseline result](experiments/qwen38-27b-b70/notes/2026-08-21-qwen38-q4km-tp1-baseline-result.md)

The missing TP1 raw aggregate-decode ladder is now
[complete](experiments/qwen38-27b-b70/notes/2026-08-25-qwen38-q4km-tp1-batched-ladder-result.md)
at directly measured parallel-sequence counts 1/2/4/8/16/32/64. Aggregate
decode rises from `24.363621` to `95.411842 tok/s`; no point is interpolated.
These `llama-batched-bench` rows are mechanism/ceiling evidence, not
quality-qualified concurrent serving. The DNN-off banner identifies Q4_K WDC
as the next bounded batched-build A/B; that two-point screen is
[in feasibility screening](experiments/qwen38-27b-b70/notes/2026-08-25-qwen38-q4km-tp1-wdc-feasibility-r3-preregistration.md).
R1 failed before measurement because a test-only forced reorder exceeded
device memory. R2 isolated Q4_K but exposed a vacuous reorder door and failed
before B64. R3 proved the harness still allocates 32,768 tokens and the broad
forced-reorder arm cannot fit; the flag-only path is closed. A source-level
Q4_K-only reorder door is now
[preregistered](experiments/qwen38-27b-b70/notes/2026-08-25-qwen38-q4km-tp1-wdc-scoped-r4-preregistration.md)
but failed before measurement: the width-1 q6_K output head still takes its
ordinary reorder path after Q4_K planes consume VRAM. A default-off q6_K
reorder suppression door is the next memory-feasibility delta; its speed cost
must be measured rather than assumed. That two-point screen is now
[rejected](experiments/qwen38-27b-b70/notes/2026-08-25-qwen38-q4km-tp1-wdc-noq6-r5-preregistration.md):
B1 fell to `21.412285 tok/s` (`0.878863x` control), B64 OOMed, and no WDC
engagement census appeared. The one-card Q4_K WDC branch is closed.
A promising point must then pass a
separate endpoint replay with sequential output oracles before package
promotion.

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

The four-card measuring host's xe driver was recovered on 2026-08-20 and again
on 2026-08-21 (after GPU3's health-failure storm re-lit on a passive query)
without FLR or reboot, each time passing per-card compute, peer access,
four-rank XCCL, a known-good exact generation canary, and a clean post-reload
journal window; see the
[second recovery note](experiments/qwen38-27b-b70/notes/2026-08-21-measuring-host-xe-recovery-2.md).
GPU3 still requires a newly preregistered fresh-root stock-health pass before
any Q64K32 use. The launch harness fails closed unless
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

0. The external 3.6 TB USB model store was not visible in `lsblk` on this host
   on 2026-08-22, while the internal NVMe had only about 12 GiB free. Do not
   place new model downloads on NVMe. The manager reported that another host
   is downloading the [55.30 GiB first-wave queue](model-intake/README.md):
   Ornith 1.5 35B Q4, Ornith 1.5 9B Q8, Nemotron 3.5 Lightning 30B Q4, and
   LFM2.5 2.6B Q8. After its downloader finishes, require direct-and-ordinary
   verification and follow the preregistered
   [bring-up protocol](model-intake/bringup-protocol.md). The shared runner
   records exact model, binary, library, source, device, and cache identities;
   its generic result is diagnostic until a model-specific quality oracle is
   registered.

1. Preserve the inactive Muse fleet and its source; verify service/process state
   again before every GPU launch.
2. Continue Qwen3.8 Q8_0 target-only TP2 from its newly qualified
   `36.726447 tok/s` strict package headline, with same-binary controls, the
   fixed cold gate, and the semantic suite. Aim for 40 tok/s without weakening
   weights, KV precision, arithmetic gates, or the two-fresh-server output
   requirement.
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
   The bounded packed MTP target/verifier FlashAttention operator screen is now
   closed as a terminal correctness rejection. Its control A1 passed, but the
   candidate-role launch for the intended Q8 x K64 stage failed the first
   checked eager KV-128 CPU-oracle replay before candidate timing or packet
   publication. Its marker/mapping record did not survive, so this rejects the
   qualification without independently proving runtime policy dispatch or the
   internal cause. Do not retry this policy,
   continue its ABBA campaign, or spend a model/full-25 run on it. See the
   [exact-shape operator preregistration](experiments/qwen38-27b-b70/notes/2026-08-20-qwen38-mtp5-m6-fa-operator-prereg.md)
   and [r6 result](experiments/qwen38-27b-b70/notes/2026-08-21-qwen38-mtp5-m6-fa-operator-result.md).
   The distinct chunk-native Q64 x K32 policy then produced a strong but partial
   operator result. On GPU2, its complete A-B-B-A sequence passed bit-exact
   eager/graph and tolerance-bounded CPU-oracle checks, plus Q/K/V/length
   mutation gates, and saved `75.17692 us/call` at KV 1300 (`1.20283072 ms`
   across the 16 full-attention calls per target step). GPU3's first selector-off
   control stopped at its first warmup synchronization before publishing a
   packet, so that campaign remains infrastructure-invalid/incomplete, not a
   qualification or candidate rejection. A fresh-root watchdog diagnostic first
   established a valid GPU3 stock-control health failure: exact stage/device/maps
   gates passed, ten asynchronous FA calls returned, `sync-enter` was sealed,
   `sync-return` never appeared, and the 60-second timeout cleanup verified an
   empty process group. Passive same-window kernel evidence records repeated
   `xe 0000:47:00.0` timeouts and resets, including one naming the exact sealed
   worker PID. Preserve both roots; do not retry, carry GPU2 evidence forward,
   run a candidate/model/full-25 arm, or infer timing/correctness. After
   the recovery and GPU3 health r2 pass, the freshly preregistered
   two-GPU eight-arm r3 then ran once and **qualified the candidate on
   both GPUs** (`q64k32-candidate-qualified-for-endpoint-campaign`):
   KV1300 paired savings `74.676`/`74.964 us/call` on GPU2/GPU3 against
   the `21.844` hurdle, ~1.2 ms per MTP5 target step, KV128 a saving
   rather than a regression, devices within 0.4%. The separately preregistered endpoint2 campaign then ran: its stock
   control arm reproduced the lane anchor (`100.928359 tok/s`
   conventional, all sealed and quality gates passed), but the candidate
   arm stopped terminal at engine-core init — the operator build lacks
   the full chunk-prefill kernel farm (0.6 MB vs 1.5 GB stock) and is
   not endpoint-deployable as built. The integration build then closed that gap (config `all`, coverage
   proven at link and by zero compiled-in miss branches), the r4
   requalification reproduced the operator savings on the new DSO, and
   the endpoint campaign series established the artifact as deployable
   and engaged with a small consistent short-KV effect (`+0.53%`/`+0.33%`
   on two completed pairs, report-only) before closing per its
   preregistered bounded-relaunch rule on the lane's own stochastic
   prompt-6 early-EOS family (three metric refusals, ~30% per-arm rate).
   The successor long-KV campaign (longkv1/longkv2, 25-row suite at KV
   ~1300/1600/1900 with bench-only ignore_eos) then **closed at its a1
   control** with two exposures and a major finding: (a) the sealed
   `max_model_len=2048` identity makes prompts above ~1535 tokens
   unservable with the mandatory 512-token window, so KV windows beyond
   ~1585 are unreachable in this lane as sealed; (b) **after the lane's
   first-ever multi-chunk prefills (eight ~1250-token rows vs
   `max_num_batched_tokens=1024`), the stock control's long-context
   needle probe degenerated to `B70_QWEN3!!!!…`** while
   arithmetic/copy/json/32x-repeat stayed green — the same probe that
   passed on the same stack under all-single-chunk history in endpoint5.
   The chunkdiag series then **isolated the mechanism locus**: dose 1
   is clean (d2), dose 8 reproduces the byte-identical degeneration
   with the 400 exonerated (d4), and the identical dose-8 exposure with
   `VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=0` is fully green (d5) — the
   persistent-scratch **reuse** path is the locus, and scratch=0 is a
   working mitigation at the tested dose — though longkv3-a1 later
   showed scratch=0 carries its own rare transient (31/32 same-boot
   repeat divergence), so neither mode is quality-clean for
   long-context serving. The instrumented p-series then excluded
   scratch field contents (full NaN poison changed nothing), pool-tail
   OOB (canary intact), and conv/ssm foreign-slot writes (per-call
   fingerprints clean) across five byte-identical reproductions; the
   remaining shape is a layout-coupled writer on the multi-chunk
   prefill path with a stable victim when the pool pins the allocator
   arena. The later isolated-cache D1/D2 program then killed two more
   mechanisms without perturbing the exact boundary: all eight requests
   released every state block with no live collision, while the native call
   saw correct fresh/continuation flags on all sixteen chunks. State-slot
   lifecycle and stale `has_initial_state` are closed; KV-page checksum or
   large adjacency-canary localization is next. Operational guidance:
   **long-context
   serving on this lane must run scratch=0 until the root cause is
   fixed**; the sealed short-KV record identity (scratch=1,
   single-chunk-only traffic) is unaffected, and all prior
   records/quality claims stand. First true long-KV incumbent data:
   ~71.6-109 tok/s conventional per row at KV~1250-1750 (content-
   dependent spread; cross-boot row nondeterminism is the known
   21-23/25 parity family, so only suite medians are usable). See the
   [closure + finding note](experiments/qwen38-27b-b70/notes/2026-08-22-qwen38-longkv2-closure-and-chunk-corruption-finding.md)
   and [longkv prereg](experiments/qwen38-27b-b70/notes/2026-08-22-qwen38-longkv-q64k32-endpoint-prereg.md).
   Serving realization of the ~75 us/call KV1300 saving therefore now
   needs the corruption fixed first, then a redesigned <=KV1585 suite or
   an unsealed-identity long-context lane. See the
   [endpoint prereg/result](experiments/qwen38-27b-b70/notes/2026-08-21-qwen38-mtp5-q64k32-endpoint-prereg.md),
   [endpoint2 result](experiments/qwen38-27b-b70/notes/2026-08-21-qwen38-mtp5-q64k32-endpoint2-result.md), and the
   [r3 preregistration](experiments/qwen38-27b-b70/notes/2026-08-21-qwen38-mtp5-m6-fa-q64k32-abba-r3-prereg.md)
   and [r3 qualification](experiments/qwen38-27b-b70/notes/2026-08-21-qwen38-mtp5-m6-fa-q64k32-abba-r3-result.md). That authorized host-wide `xe` recovery completed on
   2026-08-21 with the full post-reload gate green, and the newly
   preregistered fresh-root incumbent-control health r2 then **passed**
   (`gpu3-incumbent-control-health-pass`, complete receipt chain including
   `sync-return`, quiet journal): GPU3 stock-control health is
   re-established, and writing a fresh two-GPU eight-arm Q64xK32 operator
   campaign preregistration is now authorized (launch still requires that
   new preregistration's own gates). See the
   [r2 health preregistration](experiments/qwen38-27b-b70/notes/2026-08-21-qwen38-gpu3-incumbent-control-health-r2-prereg.md)
   and [r2 pass result](experiments/qwen38-27b-b70/notes/2026-08-21-qwen38-gpu3-incumbent-control-health-r2-result.md). See the
   [Q64 x K32 preregistration](experiments/qwen38-27b-b70/notes/2026-08-21-qwen38-mtp5-m6-fa-q64k32-operator-prereg.md)
   and [stopped result](experiments/qwen38-27b-b70/notes/2026-08-21-qwen38-mtp5-m6-fa-q64k32-operator-result.md),
   plus the [GPU3 health preregistration](experiments/qwen38-27b-b70/notes/2026-08-21-qwen38-gpu3-incumbent-control-health-prereg.md)
   and [terminal result](experiments/qwen38-27b-b70/notes/2026-08-21-qwen38-gpu3-incumbent-control-health-result.md).
   On the separate two-B70, 15-GiB reference host, the no-clock runtime-map r2
   reached and numerically passed its first stock operator call but was
   procedurally rejected by a nonportable measuring-host CPU-oracle byte pin.
   The independently reviewed r3 correction then ran once and closed the
   diagnostic as a valid positive: all four fresh same-boot workers on both
   B70s reproduced the eight frozen portable library rows with one common
   oracle digest equal to r2's, conclusively classifying r2 as a cross-host
   pin false-fail and establishing the mapped runtime identities that clock
   prerequisite 5 requires. The remote 16-arm clock campaign
   remains unauthorized pending the A1 authority commit and the remaining
   prerequisites, and the host must not run the full model. See the
   [runtime-map preregistration](experiments/qwen38-27b-b70/notes/2026-08-21-qwen38-q64k32-remote-runtime-map-diagnostic-prereg.md),
   [r2 invalid result](experiments/qwen38-27b-b70/notes/2026-08-21-qwen38-q64k32-remote-runtime-map-r2-invalid.md),
   and [r3 valid result](experiments/qwen38-27b-b70/notes/2026-08-21-qwen38-q64k32-remote-runtime-map-r3-result.md).
4. Use the official FP8 graph repro as the vLLM control and target its Triton
   GDN/state-I/O and TP2 synchronization path; simple oneCCL P2P access is
   already closed as neutral. Preserve the 9/12 GiB host cgroup.
5. Keep the archived single-card GPTQ/MTP vLLM contribution experimental: it is fast,
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
    is serialized BF16 and loaded as FP16 in this lane. A narrow eager-operator
    screen is now drafted and CPU-validated, but deliberately nonlaunchable:
    both its driver and Python qualifier fail closed. Before any arm it still
    requires separately authorized host-wide recovery, a fresh same-boot GPU3
    stock-health pass, a bounded process-group watchdog, exact post-recovery
    device binding, an enclosing campaign terminal, independent review, and
    refrozen hashes. Its strict primary gate is more than `17.092 us/call` at
    M6 on each TP weight shard; even a pass would authorize only a later
    integration experiment, not a server/full-25 run or a claim of 105 tok/s.
    The Q1 eager mtp.fc INT4 operator screen then ran (user-authorized
    2026-08-22, GPU2, eight-arm A-B-B-A under the bounded watchdog) and
    **passed** `qualified-only-for-default-off-integration-design`: W4A16
    ~33 vs FP16 ~92 us/call, ~58-60 us/call saved on both shards, all
    correctness/mutation/stability gates green, CI lowers far above the
    17.092 hurdle. This is operator-isolated eager evidence, not endpoint
    tok/s and not authorization to integrate; a default-off integration
    patch is a separate preregistered, separately authorized experiment.
    See the [mtp.fc result](experiments/qwen38-27b-b70/notes/2026-08-22-qwen38-mtp-fc-int4-operator-result.md).
    Ignore aggregate C5/C32 rows as single-stream leads. See the
    [feed audit](experiments/qwen38-27b-b70/notes/2026-08-20-localmaxxing-qwen38-external-lever-intake.md)
    and [blocked operator design](experiments/qwen38-27b-b70/notes/2026-08-21-qwen38-mtp-fc-int4-operator-prereg.md).
Qwen3.8 Flash-Next TP4 target optimization closed the default-off count-2560
combined clone-elision/event-chain A1 as a runtime negative. Replica 1 confirmed
the intended protocol on all four ranks, then all ranks lost their device queue
at the first measured-cycle synchronization after warmup. The wrapper correctly
refused replica 2; no model loaded and no timing was claimed. A tiny postflight
compute probe stalled, so further GPU work was blocked until health was
re-established. The host was subsequently rebooted and recovered; use a safer
lever. The
protected `5.515783 tok/s` MTP0 result and all other results are untouched. See
the [A1 result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-tp4-count2560-event-chain-a1-runtime-negative.md).
Clone-only follow-up is closed as low priority: A28 bounds the entire 99-copy
BF16 device family at only `0.178914-0.185792 ms/token`, a generous endpoint
ceiling of about `+0.103%`, while a correct in-place path needs a new mutating
operator rather than violating the existing functional alias contract. The
next safe component arm instead targets A28's chronic rank-2/3 submission lag
with explicit rank-process and oneCCL-worker CPU/L3 placement while leaving
accepted XCCL code and protocol unchanged. It is frozen and gated by actual
host/device health, not any boot-consumption rule. It may run whenever
its exclusive locks, unused evidence path, identity checks, and bounded
four-card preflight pass. See the
[clone analysis](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-tp4-count2560-clone-elision-analysis.md)
and [affinity preregistration](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-tp4-count2560-cpu-affinity-a1-prereg.md).
The next full-model lane is separately frozen as A31: production-M1 MoE
warps 8 by itself, preserving A29's complete battery while binding the current
default-off source descendants and the original sealed kernel stage. A30's
slower grouped-HC composite did not isolate or reject this M1 treatment. A31 is
independent of the affinity and HC-SiLU component arms and is admitted by
exclusive locks, no-clobber evidence, exact identities, host resource floors,
and bounded four-card preflight. A pass projects only about
`5.572-5.577 tok/s` and still needs a matched map-unset control plus candidate
repeat before promotion; those arms need independent run identities, not
different boots. See the
[A31 preregistration](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-tp4-mtp0-a31-moe-m1-current-prereg.md).
The next independent target-side component candidate is HC-SiLU A1. A28
measured this five-launch decomposition at `0.591987 ms/token` across 97 calls
per token. The default-off exact `[1,320]` BF16 native path is now built in an
isolated component-only runtime, with 11 CPU dispatch tests passing and no GPU
work performed. Static review removed a redundant post-kernel barrier. Build
review also rejected a mixed-SYCL-8/9 DSO before execution and rebuilt it
entirely against the accepted 2025.3/SYCL-8 ABI. Its historical frozen gate
requires exhaustive 65,536-pattern BF16 parity, production-stride and
no-mutation checks, 100-repeat stability, five-to-one launch proof, and a
`C-A-A-C` timing pass. The former fresh-boot and same-boot chain admission
rules are superseded by the lane-wide health-gated reuse policy below. All
protected rates remain unchanged. See the
[HC-SiLU preregistration](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-q38-hc-silu-a1-prereg.md).
A1 then failed closed during the exhaustive BF16 phase: chunk
`0x4100–0x423f` contained one non-NaN output-bit mismatch, so no profile,
timing, or endpoint phase ran. Exact four-card postflight and the bounded
kernel-journal gate passed, classifying this as an arithmetic correctness
negative rather than a device fault. The installed Torch `2.11.0+xpu`
reference uses `std::exp`, while A1 used `sycl::exp`; A2 changes only that
expression and adds a repeated fail-fast test for the failed region before
rerunning all 65,536 BF16 encodings. Its boot ID is provenance only and does
not block later work after clean health gates. Protected MTP0/MTP4 rates remain
unchanged. See the
[A1 result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-q38-hc-silu-a1-parity-negative.md).
A2 is now built and statically frozen as the minimal arithmetic correction.
Its isolated source differs from A1 only by `<cmath>` and `sycl::exp` to
`std::exp`; the accepted DSO links only SYCL 8, contains no fast/native-math
flag, and remains default-off and component-only. The gate repeats the exact
failed BF16 region before the complete A1 ladder. It is independent of the
affinity component and A31 and may run on any healthy boot after its exclusive
locks, unused evidence path, exact identity checks, resource floors, and
bounded four-card preflight pass. See the
[A2 preregistration](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-q38-hc-silu-a2-stdexp-prereg.md).
The lane-wide one-experiment/one-model-load-per-boot rule is deleted. Current
and future scheduling is health-gated: clean teardown and bounded postflight
permit another experiment on the same boot; an unhealthy close blocks device
work until health is re-established, with reboot reserved for last-resort
recovery. Historical packets remain unchanged evidence, but their
boot-consumption language is superseded. See the
[health-gated reuse policy](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-health-gated-reuse-policy.md).
A2 then failed closed in its first fail-fast BF16 region at raw input `0x41be`:
the Torch reference produced `0x40bd` while the `std::exp` candidate produced
`0x40be`. No exhaustive/profile/timing/endpoint phase followed, so the exact
HC-SiLU candidate and its arithmetic attribution are closed as negative. Its
four-card preflight and postflight, host recovery, journal gate, and evidence
manifest all passed. The boot remains eligible for independent work under the
new policy; the affinity component is next without a reboot. Protected rates
remain unchanged. See the
[A2 result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-q38-hc-silu-a2-stdexp-parity-negative.md).
The affinity component then ran on that same boot and closed cleanly, proving
the health-gated reuse path without a reboot. Its two pinned pairs were slower:
`-0.8993% / -0.5670%` median/p90 saving and
`-1.2163% / -1.1325%`, versus required `+5% / >=0%`. Explicit
rank-process/oneCCL-worker CPU/L3 placement is therefore closed as a component
negative with no endpoint claim. Four-card and host postflight plus the
evidence manifest passed, so the boot remains eligible and A31 can proceed
without rebooting. Protected rates remain unchanged. See the
[affinity result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-tp4-count2560-cpu-affinity-a1-negative.md).
A31 then became healthy as the third accelerator experiment on the same boot:
all 131 local-NVMe shards loaded in `69.06 s`, each rank reported
`31.57 GiB`, the intended M1 warps-8 config was selected, and `/health` returned
200. Its client failed before sending a request because it applied the old
tracked-script command-line check to the new generated inner supervisor. The
failure sentinel tore the service down; host/four-card/journal postflight and
the lifecycle manifest all passed. A31 is an orchestration negative with no
quality or speed result. Freeze a new isolated attempt with an inner-to-outer
supervisor binding check and reuse this healthy boot without rebooting. See the
[A31 result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-tp4-mtp0-a31-client-binding-negative.md).
A32 is the frozen isolated retry: attempt 32, port 19704, and new
state/run/cache/compile/RPC/supervisor/lifecycle paths. Its only behavioral
change is the client binding proof from generated inner supervisor to the
tracked outer PID/start-time and its host plus GPU0-3 locks. Independent
normalized comparison confirms the model/runtime/M1 config, quality battery,
performance selectors, and outer finalizer are otherwise identical to A31.
All static gates pass and the paths are unused. Run it on the current healthy
boot without rebooting. See the
[A32 preregistration](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-tp4-mtp0-a32-moe-m1-current-prereg.md).
A32 passed the corrected supervisor binding and completed the full battery.
Recovery, the inherited 6/7 semantic boundary, 16/16 repeat, long-context
needle, and all three protected short hashes passed. Short decode measured
`5.421586 / 5.416722 / 5.441849 tok/s`, median `5.421586`, which is
`1.70777%` below the protected `5.515783`. Its two cache-zero exact-4K rows ran
at `5.252151 / 5.189331 tok/s` but returned different non-authority hashes.
M1 warps 8 is therefore closed as a lossless short performance negative and an
exact-4K reliability negative. Teardown and every health/evidence gate passed;
the boot remains eligible without reboot. Protected MTP0/MTP4 results are
unchanged. See the
[A32 result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-tp4-mtp0-a32-moe-m1-current-negative.md).
The first compilation-free `FULL_DECODE_ONLY` graph prerequisite was a bounded
negative for the alternate `CCL_SYCL_ALLREDUCE_LL_THRESHOLD=8192` protocol.
Eager XCCL and graph replay 0 passed, but replay 1 mismatched on all four ranks
for BF16 `[1,2560]`. A later identity audit found that the protected endpoint
uses the `4096` threshold and a different `Rt64_128_PCIE` protocol; the result
therefore does not close the production graph route. No timing, endpoint, or
model load followed, and postflight remained healthy. The corrected next gate
is a no-model A/B of the same exact-changing-input probe at the production
threshold using the current libccl and the locally built public oneCCL
`4ceafd1`, whose graph-recording path uses device-side sequence state.
Protected rates remain unchanged. See the
[component result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-tp4-xpu-full-decode-graph-component-negative.md).
The corrected production-protocol A/B then established a concrete repair.
With threshold `4096`, the current endpoint libccl again mismatched on replay
1 on all ranks, while public oneCCL `4ceafd1` passed 100/100 changing-input
replays on all four ranks with 100 unique exact hashes. Its diagnostic replay
mean was `313.94`-`314.86 us/rank`, versus `4455.51`-`4455.90 us/rank` for the
fully synchronized eager oracle (`14.15`-`14.19x`). This is component evidence,
not an endpoint claim. The next gates are 97 ordered reductions in one graph
and selective-UVA PLE replay before any model load. See the
[matched-protocol result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-tp4-xpu-full-decode-graph-production-protocol-positive.md).
The target-step-sized follow-up also passed: one graph held 97 ordered,
independent BF16 `[1,2560]` reductions and replayed 100 times with every input
changed. All `9,700` outputs per rank matched the CPU oracle, all 100 composite
hashes were unique, and the inclusive graph-plus-validation mean was
`19.751`-`19.756 ms/rank`. The graph-aware library therefore clears the
collective count and ordering prerequisite. Selective-UVA PLE graph replay is
the last no-model prerequisite before an endpoint arm. See the
[97-collective result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-tp4-xpu-full-decode-graph-97-collective-positive.md).
The selective-UVA PLE prerequisite passed too. At the exact decode geometry,
one graph captured changing global row IDs, rank-local masking, FP8
`index_select` from pinned host memory, nonlocal zeroing, and the TP4 byte
reduction. All 100 replays on all ranks matched the CPU FP8 oracle and produced
100 unique hashes; the inclusive mean was `249.82`-`250.64 us/rank`. All
no-model graph prerequisites now pass with public oneCCL `4ceafd1`. Freeze one
size-1, compilation-mode-NONE, `FULL_DECODE_ONLY` endpoint arm from the
protected untuned MTP0 lane, retain synchronous PLE and the complete quality
battery, and keep every prior speed protected. See the
[PLE graph result](experiments/qwen38-flash-next-fp8-b70/notes/2026-08-31-tp4-xpu-full-decode-graph-ple-uva-positive.md).
