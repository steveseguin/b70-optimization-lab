# B70 featured-pick review — October 10, 2026

This review supersedes the earlier [size-first selection](2026-10-10-neural-download-b70-featured-picks.md). The interrupted work was already committed as `3b2f01588b`; the tracked site/catalog tree was clean. Main was fetched and fast-forward checked before editing. No unrelated lab files were changed.

## How the ranking works

This is an editorial selection, not a measured intelligence leaderboard. All 21 site families and 29 package variants are scored below, including lab replays and candidates. A site listing does **not** mean a recipe meets `recipe-publication.v2` public-source closure. Existing publication and quality states are unchanged.

Each dimension is 0–5. Total = **5P + 7C + 8O**, out of 100:

- **P, family popularity:** October 10 Hugging Face rolling downloads of the original model, not its lab quantization: at least 1M = 5; 250K = 4; 100K = 3; 10K = 2; below 10K = 1. Qwen variants inherit 5 from the Qwen family. Likes are retained as a secondary cross-check, not added to downloads. These are public-interest proxies, not unique users, market share, or a claim that more popular means better. Different distribution channels introduce bias.
- **C, recency and capability:** editorial assessment of release cohort, size/active size, supported tasks, and publisher benchmark standing. 5 = recent broad high-capability model or strong task specialist; 4 = capable current generation; 3 = compact/current or earlier capable generation; 2 = older/limited fit for this audience; 1 = small older model. Where the actual release date is unverified, it says so: repository creation is a dated availability proxy, **not a release date**. Scores do not manufacture missing benchmark results. Publisher benchmark harnesses differ, and those results are not lab measurements of our quantized recipes.
- **O, lab optimization:** 5 = current qualified exact-output/repeat result and maintained optimization work; 4 = strong scoped record with remaining repeat/replay limits; 3 = narrower/historical quality evidence; 2 = strict headline or determinism unresolved; 1 = rapid snapshot only; 0 = a lossy or compressed-KV setup excluded from default picks. Gemma earns 4.5 for its scoped quality-gated record and useful, though approximate, bandwidth-headroom evidence. Certification of model output and certification of a portable installer remain separate.

The score is a selection aid, not a sort key. After scoring, the first screen covers **seven different needs**, prioritizing the one-card audience. A high score cannot override a failed gate, a missing three-card measurement, or duplicate a role already filled. Recent publication of a package is not a model release. A newer experimental model does not displace a usable qualified one merely because it has more parameters.

[Interest snapshot](../data/neural-download-featured-source-signals-20261010.json) retains primary API URLs, model revisions, dates, downloads and likes. [Machine-readable scorecard](../data/neural-download-featured-ranking-20261010.json) contains every family and package score. Capability descriptions below cite publisher model cards through the base-model links; local quality evidence is linked separately.

## Featured order

1. [qwen38-27b-autoround-int4-b70](../models/qwen38-27b-autoround-int4-b70.html) — Everyday assistant: one-card October profile; package record is two-card. Editorial score 100/100.
2. [gemma4-26b-a4b-q8-b70-125tps-20260701](../models/gemma4-26b-a4b-q8-b70-125tps-20260701.html) — Fast single-user replies: larger one-card quality-gated package. Editorial score 89/100.
3. [qwen38-27b-fp8-vllm-tp1-b70](../models/qwen38-27b-fp8-vllm-tp1-b70.html) — Longer documents: actual 16K input measurements and full 16-bit KV. Editorial score 100/100.
4. [laguna-s-2.1-int4-b70-125tps-20260731](../models/laguna-s-2.1-int4-b70-125tps-20260731.html) — Dedicated coding: four-card specialist and teacher-exact record. Editorial score 82/100.
5. [qwen38-27b-fp8-vllm-tp2-asrock-b70](../models/qwen38-27b-fp8-vllm-tp2-asrock-b70.html) — Shared chat: exact tested 64-user answers, speed certification pending. Editorial score 100/100.
6. [qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913](../models/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913.html) — Larger demanding-task model: certified FP8 on four cards. Editorial score 100/100.
7. [ltx25-continuation-stream-b70-145f-20261010](../models/ltx25-continuation-stream-b70-145f-20261010.html) — Continuing video: distinct function, scoped timing and pending acceptance visible. Editorial score 76/100.

The first line covers one, two, three and four cards. Three-card owners are pointed to the measured two-card recipe without promising three-card scaling. The second collapsed group retains 9B options and larger alternatives/research. Only sub-9B featured alternatives go into **Small and quick**, collapsed at the bottom. The same-test table, its comparison bars, and all sections after the featured block remain unchanged.

The fast-replies role is Gemma's larger one-card quality-gated package, not a claim to be faster than every small model or every diagnostic profile. Laguna fills dedicated coding even though Flash-Next and Qwen also code: the latter fill larger-model and everyday/long-document roles. MiniMax M2.7 remains available as a historical alternative, not mislabeled as H3. The Q5 256K package is not featured: it uses compressed Q8 KV and its 262K configured capacity is not a 262K input speed measurement.

## Every cataloged model family

P/C/O are editorial scores; the total is not a benchmark. “Repo” dates below are explicitly availability proxies where a release date has not been established.

| Family and base-model source | Release / repository date | P / C / O | Total | Capability and lab basis |
| --- | --- | --- | --- | --- |
| [deepseek-coder-v2](https://huggingface.co/deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct) | Release unverified; repo 2024-06-14 | 4 / 2 / 1 | 42 | 16B / 2.4B active; older coding specialist; current cross-model standing not established here. [Lab evidence](../families/deepseek-coder-v2.json) |
| [deepseek-v4](https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash) | Release unverified; repo 2026-04-22 | 4 / 4 / 0 | 48 | Base model has strong publisher reasoning results; the lab uses a trimmed 180B checkpoint. Base capability does not transfer to that lossy target. [Lab evidence](../families/deepseek-v4.json) |
| [gemma-4](https://huggingface.co/google/gemma-4-26B-A4B-it) | [2026-04-02](https://blog.google/innovation-and-ai/technology/developers-tools/gemma-4/); repo 2026-03-11 | 5 / 4 / 4.5 | 89 | 26B / 4B active; broad multimodal family. Publisher reports competitive reasoning; mature Q8 draft record and useful modeled headroom comparison. [Lab evidence](../families/gemma-4.json) |
| [glm-4-7](https://huggingface.co/zai-org/GLM-4.7-Flash) | Release unverified; repo 2026-01-19 | 5 / 3 / 1 | 54 | 30B / 3B active; publisher SWE-bench Verified 59.2. Lab evidence is a rapid snapshot. [Lab evidence](../families/glm-4-7.json) |
| [laguna-s](https://huggingface.co/poolside/Laguna-S-2.1) | [2026-07-21](https://poolside.ai/blog/introducing-laguna-s-2-1); repo 2026-07-13 | 3 / 5 / 4 | 82 | 118B / 8B active; recent coding specialist with publisher coding comparisons. Scoped teacher-exact record; substantial projected headroom remains. [Lab evidence](../families/laguna-s.json) |
| [lfm-2-5](https://huggingface.co/LiquidAI/LFM2.5-2.6B) | Release unverified; repo 2026-07-28 | 3 / 3 / 3 | 60 | 2.6B compact model; recent but limited size for this audience. Package canaries pass; October quick-answer check does not. [Lab evidence](../families/lfm-2-5.json) |
| [minimax-m2-7](https://huggingface.co/MiniMaxAI/MiniMax-M2.7) | Release unverified; repo 2026-04-09 | 4 / 4 / 3 | 72 | 229B MoE; large general and coding model. Historical warm-run mean is weaker evidence than a current cold-suite record. [Lab evidence](../families/minimax-m2-7.json) |
| [mistral-small-3-2](https://huggingface.co/mistralai/Mistral-Small-3.2-24B-Instruct-2506) | Release unverified; repo 2025-06-19 | 4 / 2 / 1 | 42 | 24B dense vision-language model; older release and rapid lab snapshot. [Lab evidence](../families/mistral-small-3-2.json) |
| [muse-glimmer](https://huggingface.co/meta-models/Muse-Glimmer-30B) | [2026-08](https://huggingface.co/meta-models/Muse-Glimmer-30B); repo 2026-08-09 | 4 / 4 / 3 | 72 | 30B dense multimodal agent model; publisher SWE-bench Pro 51.2. Short three-prompt lab means; Q8 is not equality to BF16. [Lab evidence](../families/muse-glimmer.json) |
| [nemotron-3-5](https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16) | Release unverified; repo 2026-08-01 | 4 / 4 / 2 | 64 | 30B / 3B active; recent efficient reasoning candidate. Strict lab headline withheld; no independently matched capability rank assigned. [Lab evidence](../families/nemotron-3-5.json) |
| [nemotron-cascade-2](https://huggingface.co/nvidia/Nemotron-Cascade-2-30B-A3B) | Release unverified; repo 2026-03-18 | 1 / 3 / 1 | 34 | 30B / 3B active; publisher reasoning evaluations, but lab has only a rapid snapshot. [Lab evidence](../families/nemotron-cascade-2.json) |
| [ornith-1-5](https://huggingface.co/ornith-ai/Ornith-1.5-35B-A3B) | Release unverified; repo 2026-08-18 | 4 / 4 / 2 | 64 | 9B dense and 35B / 3B active siblings; recent coding/reasoning evaluations. Fresh-server complete-answer determinism remains unresolved. [Lab evidence](../families/ornith-1-5.json) |
| [phi-4](https://huggingface.co/microsoft/Phi-4-mini-instruct) | [2025-02](https://huggingface.co/microsoft/Phi-4-mini-instruct); repo 2025-02-19 | 4 / 1 / 1 | 35 | 3.8B older compact model; publisher MMLU-Pro 52.8. Small-model section/library only. [Lab evidence](../families/phi-4.json) |
| [qwen-14b](https://huggingface.co/Qwen/Qwen3-14B) | Release unverified; repo 2025-04-27 | 5 / 2 / 1 | 47 | 14B dense older generation; no current matched capability standing established; rapid lab snapshot. [Lab evidence](../families/qwen-14b.json) |
| [qwen-27b](https://huggingface.co/Qwen/Qwen3.8-27B) | Release unverified; repo 2026-08-05 | 5 / 5 / 5 | 100 | 27B dense; publisher SWE-bench Pro 61.7 and GPQA Diamond 89.2, under its own harness. Qualified current INT4 and FP8 variants; historical variants are scored separately. [Lab evidence](../families/qwen-27b.json) |
| [qwen-30b-a3b](https://huggingface.co/Qwen/Qwen3-30B-A3B-Instruct-2507) | Release unverified; repo 2025-07-28 | 5 / 2 / 1 | 47 | 30B / 3B active, general and coder siblings; older generation. Rapid snapshots do not match the current 27B package gates. [Lab evidence](../families/qwen-30b-a3b.json) |
| [qwen-35b](https://huggingface.co/Qwen/Qwen3.6-35B-A3B) | Release unverified; repo 2026-04-15 | 5 / 4 / 3 | 77 | 35B / 3B active; capable predecessor. Quark TP4 strict gate differs from unresolved AutoRound batch identity. [Lab evidence](../families/qwen-35b.json) |
| [qwen-flash-next](https://huggingface.co/Qwen/Qwen3.8-Flash-Next) | Release unverified; repo 2026-08-24 | 5 / 5 / 5 | 100 | 125B / 6B active plus separate n-gram embeddings; publisher GPQA Diamond 91.7 and SWE-bench Pro 62.5. Certified unchanged-target four-card result. [Lab evidence](../families/qwen-flash-next.json) |
| [qwen-9b](https://huggingface.co/Qwen/Qwen3.5-9B) | Release unverified; repo 2026-02-27 | 5 / 3 / 4 | 78 | 9B dense compact assistant; good package identity gates, but smaller and older than the main B70 choices. [Lab evidence](../families/qwen-9b.json) |
| [qwen-4b](https://huggingface.co/Qwen/Qwen3.5-4B) | Release unverified; repo 2026-02-27 | 5 / 2 / 4 | 71 | 4B dense; qualifies as small and quick, not a primary use of 32 GB. Exact package gates do not cover every concurrent profile. [Lab evidence](../families/qwen-4b.json) |
| [ltx-25](https://huggingface.co/Lightricks/LTX-2.5) | [2026-08-11 (API release; open-weight day unverified)](https://docs.ltx.io/api-changelog/); repo 2026-07-23 | 5 / 5 / 2 | 76 | 22B audio/video generation; recent native multi-shot capability. Lab continuation chunks are byte-exact; sustained speed and seam/audio acceptance are pending. [Lab evidence](../families/ltx-25.json) |

For example, Qwen's current 27B card reports SWE-bench Pro 61.7; Flash-Next reports 62.5 under the publisher's stated harness. That supports a capable model-family assessment, not a claim that our quantized deployments reproduce those scores. Poolside's release timeline places Laguna S 2.1 on July 21, despite an earlier page date and repository creation. LTX's date is the API launch, explicitly not a verified open-weight release day. Missing exact dates remain missing.

## Every published site package

P and C inherit family evidence, with a lower capability rating for Ornith's 9B sibling. O is reduced for superseded or narrower packages. The metric column is the package's stored record, **not necessarily the profile shown in the featured card**: Qwen INT4's package record is two-card, whereas its featured October check is one-card. Blank headlines remain withheld. Each value links to its existing scope and receipt; these rows are not a same-test comparison.

| Package / guide | Cards | P / C / O | Total | Stored metric (tok/s) | Selection |
| --- | --- | --- | --- | --- | --- |
| [gemma4-26b-a4b-q8-b70-125tps-20260701](../repro/gemma4-26b-a4b-q8-b70-125tps-20260701/README.md) | 1 | 5 / 4 / 4.5 | 89 | [122.160357](../data/gemma4-q8-gpu0-finalpostnorm-reproexact-full512-20260701T084728Z/summary.json) | Fast single-user replies: larger one-card quality-gated package. |
| [laguna-s-2.1-int4-b70-125tps-20260731](../repro/laguna-s-2.1-int4-b70-125tps-20260731/README.md) | 4 | 3 / 5 / 4 | 82 | [125.461973](../data/laguna-shared-elementwise-m12-record-20260731.json) | Dedicated coding: four-card specialist and teacher-exact record. |
| [lfm25-26b-q8-b70](../repro/lfm25-26b-q8-b70/README.md) | 1 | 3 / 3 / 3 | 60 | [132.137457](../data/2026-08-27-lfm25-q8-tp1-strict-headline-result.json) | Under 9B: collapsed small and quick section. |
| [ltx25-continuation-stream-b70-145f-20261010](../repro/ltx25-continuation-stream-b70-145f-20261010/README.md) | 4 | 5 / 5 / 2 | 76 | Withheld | Continuing video: distinct function, scoped timing and pending acceptance visible. |
| [minimax-m27-b70-89tps-20260520](../repro/minimax-m27-b70-89tps-20260520/README.md) | 4 | 4 / 4 / 3 | 72 | [89.314195](../repro/minimax-m27-b70-89tps-20260520/results/promoted-result-20260519.json) | Alternative: overlapping role or less complete quality evidence. |
| [muse-glimmer-30b-q8-woq-b70-100tps-20260813](../repro/muse-glimmer-30b-q8-woq-b70-100tps-20260813/README.md) | 4 | 4 / 4 / 3 | 72 | [100.368500](../repro/muse-glimmer-30b-q8-woq-b70-100tps-20260813/manifests/expected-result.json) | Alternative: overlapping role or less complete quality evidence. |
| [nemotron-35-lightning-30b-a3b-b70](../repro/nemotron-35-lightning-30b-a3b-b70/README.md) | 1 | 4 / 4 / 2 | 64 | Withheld | Alternative: overlapping role or less complete quality evidence. |
| [ornith-15-35b-a3b-q4km-b70](../repro/ornith-15-35b-a3b-q4km-b70/README.md) | 1 | 4 / 4 / 2 | 64 | Withheld | Alternative: overlapping role or less complete quality evidence. |
| [ornith-15-9b-q8-b70](../repro/ornith-15-9b-q8-b70/README.md) | 1 | 4 / 3 / 2 | 57 | Withheld | Alternative: overlapping role or less complete quality evidence. |
| [qwen35-4b-w4a16-b70](../repro/qwen35-4b-w4a16-b70/README.md) | 1 | 5 / 2 / 4 | 71 | [191.727574](../experiments/qwen35-4b-b70/data/qwen35-4b-w4a16-20260912-slu67k-strict-result.json) | Under 9B: collapsed small and quick section. |
| [qwen35-9b-fp8-b70](../repro/qwen35-9b-fp8-b70/README.md) | 1 | 5 / 3 / 4 | 78 | [98.139000](../experiments/qwen35-9b-b70/data/2026-09-07-qwen35-9b-fp8-matrix-result.json) | Alternative: overlapping role or less complete quality evidence. |
| [qwen35-9b-w4a16-b70](../repro/qwen35-9b-w4a16-b70/README.md) | 1 | 5 / 3 / 4 | 78 | [124.084255](../experiments/qwen35-9b-b70/data/qwen35-9b-w4a16-20260912-slu67k-strict-result.json) | Alternative: overlapping role or less complete quality evidence. |
| [qwen38-27b-256k-vision-mtp-b70](../repro/qwen38-27b-256k-vision-mtp-b70/README.md) | 1 | 5 / 5 / 0 | 60 | [26.668277](../repro/qwen38-27b-256k-vision-mtp-b70/README.md) | Compressed Q8 KV: no lossless default recommendation; configured capacity is not a measured long-input rate. |
| [qwen38-27b-autoround-int4-b70](../repro/qwen38-27b-autoround-int4-b70/README.md) | 2 | 5 / 5 / 5 | 100 | [117.528083](../experiments/qwen38-27b-b70/data/2026-09-05-qwen38-int4-graph-capture-tp2-mtp4-r247-result.json) | Everyday assistant: one-card October profile; package record is two-card. |
| [qwen38-27b-fp8-vllm-tp1-b70](../repro/qwen38-27b-fp8-vllm-tp1-b70/README.md) | 1 | 5 / 5 / 5 | 100 | [54.036484](../experiments/qwen38-27b-b70/data/2026-10-04-fp8-onecard-chunked-upload/tp1-pkg-32k-strict-performance.json) | Longer documents: actual 16K input measurements and full 16-bit KV. |
| [qwen38-27b-fp8-vllm-tp2-asrock-b70](../repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/README.md) | 2 | 5 / 5 / 5 | 100 | [90.309841](../experiments/qwen38-27b-b70/data/2026-09-17-fp8-comm2/tp2-ag-mtp5-strict-performance.json) | Shared chat: exact tested 64-user answers, speed certification pending. |
| [qwen38-27b-q4km-mtp2-tp1-b70](../repro/qwen38-27b-q4km-mtp2-tp1-b70/README.md) | 1 | 5 / 5 / 3 | 84 | [42.636988](../experiments/qwen38-27b-b70/data/2026-08-27-qwen38-q4km-q4mtp-tp1-mtp2-strict-result.json) | Alternative quant/runtime; current featured deployments cover the main roles. |
| [qwen38-27b-q4km-q4mtp-mtp2-tp2-b70](../repro/qwen38-27b-q4km-q4mtp-mtp2-tp2-b70/README.md) | 2 | 5 / 5 / 3 | 84 | [64.237301](../experiments/qwen38-27b-b70/data/2026-08-30-qwen38-q4km-q4mtp-tp2-mtp2-promotion-attestation.json) | Alternative quant/runtime; current featured deployments cover the main roles. |
| [qwen38-27b-q4km-tp1-b70](../repro/qwen38-27b-q4km-tp1-b70/README.md) | 1 | 5 / 5 / 3 | 84 | [27.825726](../experiments/qwen38-27b-b70/data/2026-08-21-q4km-tp1-gpu0-final-j.json) | Alternative quant/runtime; current featured deployments cover the main roles. |
| [qwen38-27b-q4km-tp2-asrock-b70](../repro/qwen38-27b-q4km-tp2-asrock-b70/README.md) | 2 | 5 / 5 / 3 | 84 | [49.717503](../experiments/qwen38-27b-b70/data/2026-08-15-q4km-tp2-q4k-glu-summary.json) | Alternative quant/runtime; current featured deployments cover the main roles. |
| [qwen38-27b-q8-q4mtp-mtp2-tp1-b70](../repro/qwen38-27b-q8-q4mtp-mtp2-tp1-b70/README.md) | 1 | 5 / 5 / 3 | 84 | [37.062028](../experiments/qwen38-27b-b70/data/2026-08-27-qwen38-q8-q4mtp-tp1-mtp2-strict-r1-result.json) | Alternative quant/runtime; current featured deployments cover the main roles. |
| [qwen38-27b-q8-tp1-b70](../repro/qwen38-27b-q8-tp1-b70/README.md) | 1 | 5 / 5 / 3 | 84 | [19.619240](../experiments/qwen38-27b-b70/data/2026-08-27-qwen38-q8-tp1-strict-reasoningoff-native-r1-result.json) | Alternative quant/runtime; current featured deployments cover the main roles. |
| [qwen38-27b-q8-tp2-asrock-b70](../repro/qwen38-27b-q8-tp2-asrock-b70/README.md) | 2 | 5 / 5 / 3 | 84 | [36.726447](../experiments/qwen38-27b-b70/data/2026-08-27-qwen38-q8-tp2-strict-reasoningoff-native-r2-result.json) | Alternative quant/runtime; current featured deployments cover the main roles. |
| [qwen38-flash-next-fp8-tp4-mtp0-w13n64-b70-34tps-20260908](../repro/qwen38-flash-next-fp8-tp4-mtp0-w13n64-b70-34tps-20260908/README.md) | 4 | 5 / 5 / 3 | 84 | [34.495292](../experiments/qwen38-flash-next-fp8-b70/data/20260908-tp4-mtp0-a326-w13n64-fresh-realistic-suite-v1-result.json) | Historical predecessor; current certified exactGDN package fills this role. |
| [qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913](../repro/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913/README.md) | 4 | 5 / 5 / 5 | 100 | [46.854250](../experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-a367-native-exact-gdn-realistic-suite-v1-result.json) | Larger demanding-task model: certified FP8 on four cards. |
| [qwen38-flash-next-fp8-tp4-mtp1-hctriton-b70-37tps-20260907](../repro/qwen38-flash-next-fp8-tp4-mtp1-hctriton-b70-37tps-20260907/README.md) | 4 | 5 / 5 / 3 | 84 | [37.045844](../experiments/qwen38-flash-next-fp8-b70/data/20260907-tp4-mtp1-a272-realistic-suite-v1-result.json) | Historical predecessor; current certified exactGDN package fills this role. |
| [qwen38-flash-next-fp8-tp4-mtp1-lossless-b70-27tps-20260905](../repro/qwen38-flash-next-fp8-tp4-mtp1-lossless-b70-27tps-20260905/README.md) | 4 | 5 / 5 / 3 | 84 | [27.048435](../experiments/qwen38-flash-next-fp8-b70/data/20260905-tp4-mtp1-a189-realistic-suite-v1-result.json) | Historical predecessor; current certified exactGDN package fills this role. |
| [qwen38-flash-next-fp8-tp4-mtp1-placement-b70-32tps-20260906](../repro/qwen38-flash-next-fp8-tp4-mtp1-placement-b70-32tps-20260906/README.md) | 4 | 5 / 5 / 3 | 84 | [31.929484](../experiments/qwen38-flash-next-fp8-b70/data/20260906-tp4-mtp1-a226-realistic-suite-v1-result.json) | Historical predecessor; current certified exactGDN package fills this role. |
| [qwen38-flash-next-fp8-tp4-mtp1-qsafused-b70-38tps-20260907](../repro/qwen38-flash-next-fp8-tp4-mtp1-qsafused-b70-38tps-20260907/README.md) | 4 | 5 / 5 / 3 | 84 | [37.825654](../experiments/qwen38-flash-next-fp8-b70/data/20260907-tp4-mtp1-a306-qsafused-realistic-suite-v1-result.json) | Historical predecessor; current certified exactGDN package fills this role. |

## Bandwidth/headroom review — projected, not measured

Intel specifies [608 GB/s per B70](https://www.intel.com/content/www/us/en/products/sku/245797/intel-arc-pro-b70-graphics/specifications.html). A division by model file size is not a valid universal token-rate ceiling: MoE activates only part of its weights, tensor parallelism communicates, KV reads depend on context, and verified drafts emit several tokens per target pass.

Instead, this review retained the site's existing ML Bottleneck workload mappings and captured an **uncalibrated** CPU evaluation of its physics engine. The [projection snapshot](../data/neural-download-featured-projections-20261010.json) records the engine URL/hash/version, full inputs, outputs and comparison fractions. This is outside the benchmark tables. The engine's physical ceiling includes modeled drafting; it is not measured memory-bandwidth utilization. Fixed representative shapes approximate varied-suite workloads, so these are editorial headroom hints only, never new results or performance promises.

| Existing modeled setup | Projected physical ceiling (tok/s), not measured | Stored rate / projection | Interpretation |
| --- | --- | --- | --- |
| gemma4-26b-a4b-q8-b70-125tps-20260701 | 173.95 | 70.2% | Approximate headroom only; quality and workload scope remain independent. |
| laguna-s-2.1-int4-b70-125tps-20260731 | 1098.83 | 11.4% | Approximate headroom only; quality and workload scope remain independent. |
| lfm25-26b-q8-b70 | 361.25 | 36.6% | Approximate headroom only; quality and workload scope remain independent. |
| minimax-m27-b70-89tps-20260520 | 426.66 | 20.9% | Approximate headroom only; quality and workload scope remain independent. |
| muse-glimmer-30b-q8-woq-b70-100tps-20260813 | 70.41 | 142.5% | Model mismatch: rate exceeds projection; excluded from optimization scoring. |
| qwen35-4b-w4a16-b70 | 295.18 | 65.0% | Approximate headroom only; quality and workload scope remain independent. |
| qwen35-9b-w4a16-b70 | 153.05 | 81.1% | Approximate headroom only; quality and workload scope remain independent. |
| qwen35-9b-fp8-b70 | 80.31 | 122.2% | Model mismatch: rate exceeds projection; excluded from optimization scoring. |
| qwen38-27b-q4km-tp1-b70 | 42.24 | 65.9% | Approximate headroom only; quality and workload scope remain independent. |
| qwen38-27b-q4km-tp2-asrock-b70 | 84.48 | 58.9% | Approximate headroom only; quality and workload scope remain independent. |

Gemma's approximate 70% of the modeled ceiling supports a mature speed path. Laguna has much more modeled headroom despite its fast absolute record. Ratios over 100% for Muse and Qwen9B FP8 are model/assumption mismatches, not impossible hardware efficiency or extra optimization credit. The engine is uncalibrated; even ratios below 100% are not an exact efficiency measurement.

Other variants are **not modeled** in this review: the current Qwen FP8 dynamic policy, Flash-Next's exact runtime, INT4's selected one-card October profile, Ornith/Nemotron withheld headlines, and video have no configuration-exact existing binding. They receive no invented bandwidth fraction. Their O scores rest on local correctness, repeat and optimization evidence. Rapid family-only reports likewise receive no projected fraction or promotion. Missing modeled headroom does not imply a slow kernel or a finished optimization lane.

## H3 and video publication boundary

October 10 owner decision supersedes the original no-package finding below: H3 is now the eighth featured pick, for independent video with audio on two cards. The [chosen Comfy-Org published pruned BF16 target and batch](../repro/minimax-h3-pruned-bf16-tp2-b70-20261004/README.md) retain their evidence limits. This is an explicit owner selection, not a new numerical interest score. LTX remains the continuing-video pick. Public rebuild closure remains incomplete.

Historical review before that decision:

**H3 is MiniMax-H3**, a 33B generator of video with synchronized audio, not MiniMax M2.7. The [publisher license](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/LICENSE) dates its release to August 2, 2026. The [lab lane](../experiments/minimax-h3-b70/README.md) and its results/notes establish the identity and retained exactness work. Searches of the family catalog, package catalog, results and notes found **no H3 site package or family page**. Its research link remains visible, with that gap stated. No new H3 publication or quality decision is implied.

LTX 2.5 is the published continuation-stream lab recipe. Its saved chunks match reference bytes, while seam/audio acceptance and sustained unthrottled performance remain open. The card describes recorded continuation, not a promise that a server is live now. No host service was inspected, launched or touched.

## Generation, validation and deployment

Editorial source: [featured_picks.py](../tools/featured_picks.py), called by the existing model-page generator. The package catalog is regenerated from manifests, never edited by hand. The same `87c8c71933` publication path is used: package catalog validator, family and model generators, public summary synchronization, then GitHub Pages from `main:/`.

The [CPU validation receipt](../data/neural-download-featured-ranking-validation-20261010.json) records checks. Publication uses explicit-path commits on main with the requested co-author. No GPU, server, systemd, port 8188 or `/dev/dri` access is part of this task. Heavy CPU commands run at nice 19 with `OMP_NUM_THREADS=2`. Projection downloads used auto-cleaned temporary directories.
