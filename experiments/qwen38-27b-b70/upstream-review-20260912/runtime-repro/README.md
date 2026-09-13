# Runtime reproductions on stock vLLM XPU images — 2026-09-12 (afternoon)

Companion to [../README.md](../README.md) (source-level review, prefill comment on #51562, kernels issue #593,
phantom held). This packet answers the question the morning review left open: **which of the lab's recorded
"bugs" still reproduce end-to-end on stock upstream images, on this host, with no lab code**, and what to do about
each. Model for the dynamic-speculation arms: Qwen3.5-9B W4A16 (RedHatAI), one B70 (`ZE_AFFINITY_MASK=0`),
schedule `[[1,8,3],[9,16,1],[17,64,0]]` (K=3 for 1–8 users, K=1 for 9–16, no drafts from 17), `--max-model-len 256`,
64-prompt small-context suite, greedy, `ignore_eos`, sequential oracle comparison. Runners: `run-mrv2-dsd-k0-v2.sh`
(`ARMS`, `CONC`, `OUTPFX` env), `run-phantom-v2.sh`, `queue4.sh`. Raw server logs stay under
`/mnt/fast-ai/bench-results/upstream-repro-20260912/` (sha256 in each subdirectory); excerpts are here.

## Images

| tag | image id | vLLM | vllm-xpu-kernels |
| --- | --- | --- | --- |
| nightly-0825 (`vllm/vllm-openai-xpu:nightly` as pulled 08-25) | c345345f | 0.26.1rc1.dev1177+ga9a17e709 | 0.1.13.2 |
| v0.29.0 (`vllm/vllm-openai-xpu:latest`, sha256:96db42e2) | 96db42e2 | 0.29.0 | 0.1.14.1 |
| v0.29.0-pr53542 (v0.29.0 + only the `gdn_attn.py` hunks of open PR #53542, head e981ca59) | 2028c399 | 0.29.0 | 0.1.14.1 |
| nightly-0912 (`vllm/vllm-openai-xpu:nightly`, sha256:5de5a541, pulled 09-12) | 5de5a541 | 0.1.1.dev50+geed1f3d0c | 0.1.14.1 |

## Results

| image | runner | 1 user | 12 users (K=1) | 64 users (ramp: prefills + drafts; drain: 16→1 users) |
| --- | --- | --- | --- | --- |
| nightly-0825 | MRV2 | engine dies in `warmup_kernels`: `causal_conv1d does not support spec-decode and non-spec (prefill + decode) tokens in the same invocation` | – | – |
| nightly-0825 | MRV1 | 69.3 tok/s, exact | – | dies on the ramp (19 new prefills + 1 decode carrying 3 drafts): same mixed-batch error |
| v0.29.0 | MRV2 | 71.0, exact | – | ramp passes; **dies in the drain at 11 running requests with 1 draft each**: `Expected spec_token == num_spec_decodes * (num_speculative_tokens + 1)` (22 tokens, kernel expects 44) |
| v0.29.0 | MRV1 | 69.2, exact | **dies immediately** (12 requests × 2 tokens = 24; kernel expects 48) | dies in the drain at 13 running requests (26 vs 52) |
| v0.29.0-pr53542 | MRV1 | 69.1, exact | **242.9 tok/s, 12/12 exact, complete** | 1083 tok/s, complete, 61/64 exact, no engine error |
| v0.29.0-pr53542 | MRV2 | 70.9, exact | 496.4 tok/s, 11/12 exact, complete (see below) | 896 tok/s, complete, 61/64 exact, no engine error |
| nightly-0912 | MRV2 | 71.0, exact | see 12-user row below | dies in the drain, same assertion (11 running requests × 2 tokens vs 44 expected) |
| nightly-0912 | MRV1 | 69.3, exact | see 12-user row below | dies in the drain, same assertion (13 × 2 vs 52) |
| nightly-0912 (12-user rung) | MRV1 | 69.3, exact | **dies immediately**, same assertion | – |

Non-exact rows on the patched image (`benchmark-c011` at token 12 on both runners at their 12- or 64-user rung; `rollback-c018`,
`capacity-c022`, `rollback-c050` at tokens 3–5 on MRV2 c64; `testing-c037`, `rollback-c042` on MRV1 c64) were not
logprob-checked here; they are the pattern of the lab's concurrency near-ties, not engine errors. The 61/64 at 64 users on the patched image is the lab's known concurrency near-tie behaviour of speculation
without the 5 ms admission stagger (the 9B note of 2026-09-10 lists 62/64 for static depth 3 on the lab build); it is
not an error and every output completed. The crashing batches were read from vLLM's own `dump_input` scheduler dump in
each server log (`scheduled_spec_decode_tokens` lists one draft per request; `total_num_scheduled_tokens` = 2 × batch).

## Decisions per recorded item

| lab item | status upstream | this packet's evidence | decision |
| --- | --- | --- | --- |
| Mixed spec + non-spec tokens in one `causal_conv1d` call (prefill joins a batch carrying drafts) | vLLM #53928 (open); fixed by kernels PR #537 + vLLM PR #48109, both merged 08-19; kernels 0.1.14 released 08-31 | reproduces on nightly-0825 (kernels 0.1.13.2) in both runners; **does not reproduce on v0.29.0** (kernels 0.1.14.1): the same ramp passes | no PR. Optional: evidence comment on #53928 that v0.29.0 resolves it, so it can be closed. |
| Reduced active speculative width rejected by the GDN host contract (kernels #593, filed this morning from source + isolated native operator tests) | kernels #593 open (no fix PR); vLLM PR #53542 open since 08-24, review required, no reviewer comment yet | **first end-to-end reproduction on stock v0.29.0**: any dynamic schedule whose smaller K is reached kills the server (12 users, or the drain of a larger batch). PR #53542's `gdn_attn.py` hunks alone, on the unchanged 0.1.14.1 kernels, remove the crash and the K=1 rung is exact | **no kernels PR**: the fix belongs on the vLLM side and already exists as #53542. Support it with the B70 end-to-end evidence (draft in `drafts/`), and point #593 at it. |
| MRV2 speculator capture asserts in `InputBatch.make_dummy` on the K=0 range (lab build 0.27.2rc1.dev77) | vLLM #51510 / PR #51575 / PR #49652 open | v0.29.0 MRV2 boots, captures and serves with the schedule; K=1 range drafts one token per request | no PR; nothing to add beyond "not seen on v0.29.0". |
| K=0 steps still pay the draft forward | vLLM #53420, PR #53426 (opt-in skip) open | not measured here | no PR. |
| oneDNN fp16 GEMM run-to-run nondeterminism at 129+ rows for small-N shapes; `torch.use_deterministic_algorithms(True)` removes it | not a vLLM defect (oneDNN split-K kernel selection); vLLM never enables deterministic mode | lab census 2026-09-12 (4B probes) | lab lever tested and closed: R295 overlay (`VLLM_XPU_TORCH_DETERMINISTIC=1`) costs 29% at 64 users under speculation, lifts exactness by ~4 rows of 64 and makes passes less repeatable (4B note 2026-09-12 "torch deterministic mode is not a lever"). Not a vLLM bug either way. |
| `xpu-smi health` fails on this driver (v3 engine) | tooling, not vLLM | – | none. |
| Copy-engine reset (`engine_class=bcs`, `Fault response: -EINVAL`) on card e3:00.0 during R300 mtp1-b model load | vLLM #55425 (open, another B70 user: Qwen3.8-27B INT4, MTP2 at 160K context, bcs reset with a page fault; MTP1 stable) | three occurrences this boot (12:46 lab image; 16:02 stock v0.29.0 eager arm; 20:00 stock nightly async-off arm), all right after weight load, all card e3:00.0 = Level Zero index 1, all `bcs` with page-fault lines; index 0 ran every single-card job today without incident | none now: our faults are at weight load, not at long-context MTP2 like #55425. Reboot, then see whether it recurs on a fresh boot. |
| Historical MTP2 "phantom first token" on the 09-03 stock image | held (see `../phantom/REVIEW.md`) | phantom arms on v0.29.0 and nightly-0912 queued (four servers each; results appended below when done) | does not reproduce on v0.29.0 or nightly-0912 (8/8 arms clean): nothing to file. |

## Posted evidence

Both comments were posted 2026-09-12 evening and read back (`comment-receipts.json`):

- [vLLM PR #53542](https://github.com/vllm-project/vllm/pull/53542#issuecomment-5649889561): B70 before/after table.
- [kernels issue #593](https://github.com/vllm-project/vllm-xpu-kernels/issues/593#issuecomment-5649890209): points at that PR.

## Phantom arms (stock Qwen3.8-27B FP8, TP2, MTP depth 2, R192/R194 shape: sequential oracle then 64 prompts at once)

| image | arm | first-token outliers (64 rows) | note |
| --- | --- | --- | --- |
| v0.29.0 | default compile, async on | none | `cache-c032` head `[271, 3833, 14542]` (normal); 5/64 exact at 64 users (stock W8A16 run-to-run nondeterminism, as on 09-03) |
| v0.29.0 | default compile, `--no-async-scheduling` (the 09-03 phantom arm) | none | same head; 3/64 exact |
| v0.29.0 | `--enforce-eager` (1), first attempt 16:01 | **hung after model load**; kernel logged `Engine reset: engine_class=bcs` + `Timedout job` on card e3:00.0 at 16:02:44 | second copy-engine fault on this card this boot (first: 12:46, R300 mtp1-b, also at load). Queue stopped; the user chose to continue on this boot |
| v0.29.0 | `--enforce-eager` (1), rerun 19:37 | none | healthy in 2 min, ran clean |
| v0.29.0 | `--enforce-eager` (2) | none | ran clean |
| nightly-0912 | default compile, async on | none | `cache-c032` head normal; 7/64 exact |
| nightly-0912 | default compile, `--no-async-scheduling`, first attempt 19:59 | **hung after model load**, third `bcs` engine reset on e3:00.0 at 20:00:24 | two-card work stopped; host rebooted at 20:44 (boot dc3e2634) |
| nightly-0912 | default compile, `--no-async-scheduling`, rerun after reboot | none | 5/64 exact; `cache-c032` head normal |
| nightly-0912 | `--enforce-eager` (1) | none | 7/64 exact; head normal |
| nightly-0912 | `--enforce-eager` (2) | none | 5/64 exact; head normal |

Phantom verdict: **not reproduced in any of the eight stock arms** (four on v0.29.0, four on nightly-0912, R192/R194 shape),
including the arm and prompt that showed it on 09-03. Every output completed; the kernel log of the new boot has no engine
resets. The historical report stays held; there is nothing to file. The copy-engine fault is a host/driver event during weight load on one card (e3:00.0, Level Zero index 1), seen three
times this boot with a lab image and two stock images; it is not tied to speculation depth (compare #55425) and is recorded in
`phantom-v0.29.0/kernel-engine-resets-today.txt`. Single-card work on index 0 continued without incident.
