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
