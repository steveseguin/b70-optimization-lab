# Gemma 4 26B A4B Q8: does the LAN service read prompts at the slow or the fast conversion speed? (2026-10-15)

Registered before it runs.

**Why.** The LFM2.5-24B work found that, once the first decode step has reordered the Q8_0 weights, llama.cpp's SYCL
prompt path converts them to FP16 for every prompt step with `dequantize_block_q8_0_reorder`, and that kernel's speed
depends on the build: the published LFM2.5 build read prompts about a third slower than a build with a coalesced
conversion (`LLAMA_SYCL_Q8_0_REORDER_DEQ_COALESCED=1`, same bytes). See
`experiments/lfm25-24b-a2b-b70/notes/2026-10-14-lfm25-24b-a2b-bringup.md`, 2026-10-15 sections. Gemma's production
build has the same kernel and runs with `LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER=1`.

**Test build.** A copy of the production source tree (`git diff` identical except `ggml/src/ggml-sycl/convert.cpp`,
which gets only the LFM2.5 work tree's conversion change and the off-by-default counters), configured with the
production build's CMake settings, built into a new folder. The production binary is not touched.

**Check** (`scripts/gemma-prefill-check.sh`): the LAN service moves to card 0 (throughput-card0) and is put back on its
throughput recipe at the end; test servers run on card 1 through the production launcher (service profile, one user,
32K): production binary twice, the test build with the new kernel twice, and the test build with the old kernel once.
Each answers one 32-token reply, then the 2K / 8K / 24K prompts are timed twice by the server's counters.

**Reading.** If the production binary reads prompts clearly slower than the test build with the new kernel, the
service is in the slow state and the new kernel is worth an identity check against the production outputs (the
Gemma lane's suites) before any change to the service. If they match, the service is in the fast state and nothing
changes. Speed only; no change to the LAN service is made by this check.

## Result (19:00-19:14)

Server prompt rate (tok/s, the server's own counters, after one 32-token reply; rep 1 / rep 2):

| Server | 2K prompt (1,867 tokens) | 8K (7,623) | 24K (29,400) |
|---|---|---|---|
| production binary, a | 1,448 / 1,854 | 1,510 / 1,533 | 1,085 / 1,084 |
| production binary, b | 1,441 / 1,857 | 1,490 / 1,532 | 1,079 / 1,084 |
| test build, old kernel | 1,436 / 1,854 | 1,498 / 1,531 | 1,080 / 1,084 |
| test build, new kernel, a | 1,569 / 2,146 | 1,695 / 1,739 | 1,174 / 1,178 |
| test build, new kernel, b | 1,569 / 2,150 | 1,694 / 1,739 | 1,172 / 1,178 |

The service is not in the slow state LFM2.5 v2 was in (the test build with the old kernel matches the production
binary to 0.2 %), but the new kernel still reads prompts faster: +16 % (2K), +13 % (8K), +9 % (24K), the same on both
servers. That passes the reading rule, so the new kernel goes to an identity check before any change to the service.
No kernel fault lines; the LAN service was restored to its throughput recipe at 19:14.

### Identity check (registered 2026-10-15 19:20, before any run)

`scripts/gemma-identity-check.sh`, same setup (test servers on card 1 through the production launcher, service
profile, one user, 32K; the LAN service on card 0 meanwhile):

1. **verify**: the test build with `LLAMA_SYCL_Q8_0_REORDER_DEQ_COALESCED=2`, which runs the old and the new
   conversion on every call and compares their outputs byte by byte, through the 12-prompt realistic suite (512 tokens,
   greedy, no prompt cache) and the 2K / 8K / 24K prompts (128 tokens). **Pass:** calls > 0 and 0 mismatched calls.
2. **prod** (production binary) and **new** (test build, flag 1), each on a fresh server: the same suite and long
   prompts, the long prompts with top-8 logprobs. **Pass:** suite 12/12 token-identical and long prompts bit-exact
   (max |dlogprob| 0), prod vs new.

If both pass, the service change (the test build's binary and the flag in the production launcher) is offered to the
owner with the numbers; it is not made by this check.
