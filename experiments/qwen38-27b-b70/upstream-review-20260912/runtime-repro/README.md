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
| oneDNN fp16 GEMM run-to-run nondeterminism at 129+ rows for small-N shapes; `torch.use_deterministic_algorithms(True)` removes it | not a vLLM defect (oneDNN split-K kernel selection); vLLM never enables deterministic mode | lab census 2026-09-12 (4B probes) | lab lever only: R295 overlay (`VLLM_XPU_TORCH_DETERMINISTIC=1`), 4B det1/det0 chain queued behind this queue. |
| `xpu-smi health` fails on this driver (v3 engine) | tooling, not vLLM | – | none. |
| Copy-engine reset (`engine_class=bcs`, `Fault response: -EINVAL`) on card e3:00.0 during R300 mtp1-b model load | vLLM #55425 (open, another B70 user: Qwen3.8-27B INT4, MTP2 at 160K context, bcs reset with a page fault; MTP1 stable) | one occurrence here, MTP1, short context, at load; no reproduction attempted (reboot pending) | none now; a data-point comment only if it recurs after the reboot. |
| Historical MTP2 "phantom first token" on the 09-03 stock image | held (see `../phantom/REVIEW.md`) | phantom arms on v0.29.0 and nightly-0912 queued (four servers each; results appended below when done) | file only if it reproduces on a current image. |

## Pending rows
The phantom arms (four stock 27B FP8 TP2 servers per image, v0.29.0 then nightly-0912) are appended by hand when `queue4.sh` finishes.
