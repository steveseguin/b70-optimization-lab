# Gemma Dashboard Transfer Ideas

Date: 2026-06-12

Source snapshot:

- Dashboard: `https://huggingface.co/spaces/gemma-challenge/gemma-dashboard`
- Organization page: `https://huggingface.co/gemma-challenge`
- Workspace guide:
  `https://huggingface.co/buckets/gemma-challenge/gemma-main-bucket/tree/README.md`
- Eval prompts:
  `https://huggingface.co/datasets/gemma-challenge/eval-prompts`
- Public API sampled:
  `https://gemma-challenge-gemma-bucket-sync.hf.space/v1/digest?limit=20`

This is about ideas for our Gemma lanes. It is not a Qwen3.6 speed result and
does not change the Qwen accepted endpoint.

## Useful Facts From The Challenge

- Target model is `google/gemma-4-E4B-it`, not our local Gemma 4 12B lane.
- Official hardware is single `a10g-small` with 1x NVIDIA A10G 24GB, not B70 or
  multi-GPU.
- Scoring is single-stream TPS. This matches our single-request latency focus
  better than aggregate serving benchmarks.
- Quality is enforced by PPL. The public guide says the validity cap is
  reference PPL plus 5%, around `2.42` when the reference is around `2.30`.
- The benchmark requires OpenAI-compatible serving that supports token-ID
  prompts, `prompt_logprobs`, and `add_special_tokens: false` for PPL scoring.
- Greedy decode is expected to remain token-identical to plain greedy
  autoregressive decode of the same submitted checkpoint.
- Current top public rows around `420 TPS` combine serving/runtime tricks:
  `lmhead12k`, `fa2sw`, public-prompt prefix-cache warming, one-graph/loopgraph
  decode, drafter/verifier work, fused accept/prep, and detokenization cleanup.
- Several private verification messages show that high self-reported TPS can be
  invalidated when private-set rerun TPS drifts by more than the verifier
  tolerance, even if PPL stays under the cap. Do not trust a single best draw.

## Transferable Ideas For Our Gemma

1. **Use PPL as a first-class speed gate.**
   Our Gemma quality gate should report both speed and PPL or a close proxy,
   plus exact canaries. A speed result that cannot run prompt-logprob scoring
   should be considered incomplete.

2. **Separate benchmark-safe prefix warming from production-safe prefix caching.**
   The challenge top row warmed the public prompt prefixes before readiness.
   That is useful for leaderboard mechanics but risky for production. The
   production-safe version for us is static system-prefix, tool-schema, and
   repeated-workflow prefix caching with explicit cache-hit telemetry.

3. **Investigate lm-head keep-set pruning with full-head fallback.**
   `lmhead12k` appears repeatedly in the best Gemma stack. For our Gemma, build
   a workload-specific vocabulary heatmap and test a fast restricted logits
   path only if a fallback preserves exact greedy output. Full logits remain
   mandatory for prompt-logprobs/PPL and for any token outside the keep set.

4. **Audit sliding-window/local attention execution.**
   The `fa2sw` frontier implies a real gain from serving sliding-window
   attention as sliding-window attention instead of accidentally doing full
   attention work. For our Gemma, verify each local/sliding layer's effective
   attention span and backend path on XPU.

5. **Measure drafter acceptance before changing speculative depth.**
   The public acceptance histogram shows K-depth can be exhausted; the valuable
   target is the zero-accept bucket, not blindly increasing K. For our Gemma,
   add an acceptance histogram that samples without per-step device-to-host
   synchronization.

6. **Respect exact-fidelity details in custom kernels.**
   Recent challenge messages called out partial RoPE, reading the model's live
   `cos_sin_cache`, BF16 rounding at operator boundaries, and deterministic
   tie-breaking as sources of drift. Any custom Gemma kernel or speculative
   verifier needs these details before speed matters.

7. **Avoid per-token host synchronization.**
   One public diagnostic reported instrumentation-deflated throughput around
   `364 TPS` versus the `418-420 TPS` family, attributing a large cost to
   per-step host work/sync. For us, device rings and interval dumpers are the
   right pattern; per-token CPU reads are not.

8. **Use paired multi-draw A/B, not best-draw fishing.**
   The public frontier reports wide draw bands even for byte-identical packages.
   For our Gemma, require multiple paired runs with mean/spread, then promote
   the stable improvement, not a lucky sample.

9. **Keep multimodal behavior explicit.**
   The challenge disallows disabling text/image/audio capability for speed.
   Our Gemma 4 local lane should record whether image/audio are intentionally
   supported, stubbed, disabled, or out of scope. Speed numbers should state the
   capability surface.

10. **Publish exact manifests and immutable evidence.**
    The challenge's `manifest.json` plus `serve.py` plus artifact bucket pattern
    is worth copying. Our GitHub notes already do this partially; Gemma
    experiments should include the exact command, model revision, cache state,
    PPL/quality summary, and raw benchmark JSON.

## Bigger Gemma Ideas To Try

1. **Dual logits mode.**
   Fast restricted lm-head for normal greedy decode, full lm-head for PPL,
   prompt-logprobs, and fallback. The gate is token identity versus full
   logits, not approximate PPL alone.

2. **Static prefix/service-profile lanes.**
   Make separate serving profiles for known repeated chat/system/tool prefixes
   and general unknown prompts. This is the production-clean version of public
   prompt pre-cache.

3. **Gemma-specific sliding attention microbench.**
   Build a small harness that times every Gemma attention layer by effective
   window size, backend, context length, and graph-capture state. Promote only
   changes that preserve token/PPL gates.

4. **Speculative verifier with acceptance histogram first.**
   Before training or integrating any drafter, run an exact-target verifier
   harness that records accept lengths, zero-accept cases, rollback cost, and
   per-step sync cost.

5. **Kernel fidelity checklist.**
   For each custom Gemma kernel: prove partial RoPE handling, live cache use,
   BF16 boundary behavior, tie-breaking, and full-output parity on a fixed
   prompt bank before benchmarking.

6. **Variance-aware leaderboard discipline.**
   Store every draw, including bad draws, and require private-like prompt
   reruns. A speed claim should survive both PPL and run-to-run variance.

7. **Prompt-logprob compatibility audit.**
   Confirm our current Gemma vLLM endpoint can accept integer-token prompts,
   disable special-token insertion, and return `prompt_logprobs`. If not, fix
   that before serious PPL-gated optimization.

## Fast Gemma E4B Frontier Follow-Up 20260613

The live dashboard's top public row moved to `470.526 tok/s` on
`google/gemma-4-E4B-it` after the original notes were written. The useful
signal is not the absolute TPS or the challenge-specific stack; it is the
shape of the control plane and validation contract.

Observed frontier ingredients:

- A onegraph/vLLM-derived served decode path.
- A captured `K=7`, width-1 propose graph.
- Fused accept/prep bookkeeping.
- `choices[0].token_ids` returned for every decode record.
- Exact prompt-logprob/PPL fallback through the original dense forward path
  when scoring requests arrive.
- Readiness-gated prefix-cache warmup of the 128 public benchmark prompts.
- Full artifact trail: summaries, decode outputs, PPL outputs, environment,
  server config, and logs.

Important caveat:

- The top row explicitly calls itself a benchmark-specific precache
  composition, not a native runtime result. The same note says local exact
  decode-token comparison against its previous baseline was not token-identical,
  while the official decode contract and PPL gate passed. For our work, that is
  a warning: public benchmark validity is useful, but production promotion still
  needs our stricter byte/token parity canaries.

Actionable items for our Gemma lane:

1. **Token-ID decode contract.** Add or verify an endpoint mode that returns
   token IDs for every decode record. This makes speed/quality comparisons less
   dependent on detokenization timing and string formatting.
2. **Exact PPL fallback path.** Keep a full-original-forward path for
   `prompt_logprobs` and PPL even if normal generation uses a captured or
   fused fast lane.
3. **Readiness-only warmup accounting.** Warm real production prefixes before
   readiness, but report benchmark-prompt warmup separately and never as a
   general cold-prompt claim.
4. **Captured width-1 propose graph.** For Gemma, prototype a captured
   single-token propose/decode graph before spending time on wider speculative
   depth. Width-1 removes scheduler overhead without needing model changes.
5. **Fused accept bookkeeping.** If speculative decode is revisited, fuse
   accept/prep only after acceptance histograms and rollback parity are working.
6. **Artifact parity bundle.** Every Gemma speed run should ship the same class
   of artifacts: exact command, env, model revision, cache state, decode token
   IDs, PPL/logprob results, and raw logs.

## Dashboard Refresh 20260613j

The latest public dashboard API snapshot is recorded in
`data/gemma-dashboard-results-summary-20260613j.json`.

Snapshot details:

- Parsed rows: `354`.
- Top public row: `470.526 tok/s`, PPL `2.37794`,
  method `mao-gemma-fast-lf29pc-v1`.
- Recurring keywords in result notes: `graph=219`, `capture=143`,
  `prefix=111`, `vllm=88`, `speculative=60`, `lm_head=43`,
  `fallback=35`, `prompt_logprobs=14`, `detok=9`, `precache=8`,
  `negative=147`, and `ppl=354`.

What changes from this refresh:

- The board keeps converging on a fast decode path plus exact scoring fallback.
  For our own Gemma work, that supports a two-lane implementation: optimized
  generation for live serving, exact original-forward scoring for PPL and
  prompt-logprob requests.
- The result feed is capture-heavy, but the useful production version is a
  named readiness state: graph captures, route packs, and safe prefix caches
  should be measured as warmup artifacts, not hidden inside cold-prompt speed
  claims.
- The `lm_head`/detok/fused-accept cluster is worth a Gemma-specific timing
  probe. Any restricted logits path needs a full-head fallback and exact
  token-ID parity before speed claims.
- The large number of negative result notes is a process lesson: keep failed
  scheduler, graph, and speculative attempts in the repo with exact commands so
  we do not repeat them.
- None of this changes the Qwen3.6 path. The dashboard is Gemma E4B on
  challenge hardware, so its absolute TPS is only a signal for ideas and
  validation discipline.

## Dashboard Refresh 20260613k

The user flagged the live Fast Gemma dashboard again as a source of ideas for
our own Gemma acceleration work. I refreshed the compact snapshot in
`data/gemma-dashboard-results-summary-20260613k.json`.

Snapshot details:

- Parsed rows: `354`.
- Top public row: `470.526 tok/s`, PPL `2.37794`,
  method `mao-gemma-fast-lf29pc-v1`.
- The top-10 rows are still clustered around the same ingredients:
  fast onegraph/loopgraph-style decode, `lmhead12k` or logits restriction
  experiments, `fa2sw` sliding-window attention handling, public prompt
  precache/prefix warmup, and exact PPL/prompt-logprob fallback.
- Recurring keyword counts are unchanged enough to treat the trend as stable:
  `graph=219`, `capture=143`, `prefix=111`, `vllm=88`,
  `speculative=60`, `lm_head=43`, `fallback=35`,
  `prompt_logprobs=14`, `detok=9`, `precache=8`, `negative=147`,
  and `ppl=354`.

Gemma transfer matrix:

1. **Try first: Gemma logits/lm-head timing probe.**
   The board repeatedly found output-head/logits work worth isolating once the
   body was optimized. For our Gemma lane, add a profile that separates final
   norm, lm-head matvec, logits postprocess, sampler, detok, and response
   streaming. Only after this timing exists should we prototype restricted
   logits or keep-set paths.

2. **Try first: full-head fallback for any restricted logits path.**
   A workload-specific keep-set can be production-safe only if the endpoint can
   immediately fall back to the full head whenever the restricted lane is not
   provably exact. Promotion gate: identical token IDs against the full head on
   a fixed prompt bank plus full `prompt_logprobs` compatibility through the
   reference path.

3. **Try first: sliding-window attention audit.**
   The `fa2sw` cluster is a reminder to prove that Gemma local/sliding layers
   are actually executed with their intended window, not accidentally routed
   through full attention or a slow fallback. Measure by layer, context length,
   graph state, and backend.

4. **Try first: token-ID streaming with delayed detok.**
   Several frontier notes treat detokenization and response formatting as real
   overhead. Add an internal token-ID stream and an end/chunk detok path with
   byte-identical reconstruction. This should be a low-risk production cleanup
   because it cannot change the sampled token.

5. **Try first: two-lane eval contract.**
   Keep normal generation on the fastest exact decode lane, but route PPL,
   prompt-logprob, provenance, and audit requests through a reference-compatible
   original-forward lane. The two lanes must be continuously sampled for token
   parity.

6. **Try later: captured width-1 decode/propose graph.**
   The frontier has captured single-token propose/decode shapes before going
   wider. For our Gemma lane this is attractive because it attacks scheduler
   and dispatch overhead without depending on speculative acceptance quality.

7. **Try later: acceptance telemetry before any speculative depth.**
   The dashboard has both speculative wins and many speculative negatives. Do
   not tune depth or drafter choice until we log accept length, zero-accept
   rate, verifier cost, rollback cost, and whether speculation disables async
   scheduling in the chosen backend.

8. **Avoid as a production claim: public benchmark prompt precache.**
   It is useful for understanding the challenge leaderboard, but it should not
   be reported as general prompt speed. The production-clean analogue is
   readiness-gated warming of real system prompts, tool schemas, safety prompts,
   and known workflow prefixes, reported separately from cold-prompt latency.

9. **Avoid as a quality shortcut: PPL-only acceptance for fast lanes.**
   The challenge can approve rows through its public contract even when local
   token comparison against a previous baseline is not exact. Our stricter bar
   remains token-ID parity, exact canaries, and a reference scoring path before
   any production promotion.

Concrete next Gemma task:

- Build a small `gemma-profile-lmhead-detok` harness before touching kernels:
  fixed prompt bank, greedy decode, token IDs, timings for final norm, lm-head,
  sampler, detok, response write, and reference `prompt_logprobs`. This tells
  us whether the Gemma dashboard's lm-head/logits lesson maps to our Gemma
  model or is mostly E4B/challenge-specific.

## Dashboard Source Check 20260613m

The user pointed to the live Gemma dashboard again. I re-fetched the public
`/api/results` endpoint and compared it against the latest tracked compact
snapshot, `data/gemma-dashboard-results-summary-20260613k.json`.

No new idea-bearing rows were visible:

- Current live row count: `354`; tracked snapshot row count: `354`.
- Current top row: `470.526 tok/s`, method `mao-gemma-fast-lf29pc-v1`;
  tracked snapshot top row is the same.
- Keyword counts were unchanged for `graph`, `capture`, `prefix`, `vllm`,
  `speculative`, `lm_head`, `fallback`, `prompt_logprobs`, `detok`,
  `precache`, `negative`, and `ppl`.

Decision:

- Do not add another redundant dashboard snapshot for this check.
- Keep the existing transfer matrix as current.
- Continue using the board as a methodology source only: captured decode
  lanes, exact eval fallback, readiness-gated warm artifacts, and preserved
  negative runs.
- For Qwen3.6, the matching actionable artifact is
  `data/qwen36-forward-bottleneck-decision-20260613m.md`, which points back to
  model-forward/forward-stream dependencies rather than output-tail work.

## Dashboard Runtime Source Check 20260613n

The user linked the dashboard again as a source of ideas. I checked the live
result API into `/tmp` and re-read the current Space source. The result feed is
still not new enough to warrant another tracked snapshot:

- Current live row count: `354`.
- Top row: `470.526 tok/s`, PPL `2.37794`, method
  `mao-gemma-fast-lf29pc-v1`.
- Keyword counts remain stable versus the tracked
  `data/gemma-dashboard-results-summary-20260613k.json` snapshot.

The useful new signal is in the dashboard service code, not the leaderboard
values:

- The Space warms the message/results/agent listing cache in the background so
  the first user request is not forced to pay cold fanout.
- It follows paginated Hub bucket tree listings, fixing the silent 1000-file
  ceiling that had hidden newer files from the message board.
- It caches immutable file content by a content validator (`xetHash`, with
  size/mtime fallback), so polling mostly fetches the tree and only new files.
- It bounds concurrent file fetch fanout with `HUB_FETCH_CONCURRENCY`.
- It fronts Hub-backed endpoints with a TTL single-flight cache and
  `asyncio.shield`, so one cancelled client does not cancel the shared refresh.
- On refresh failure it serves the last good value instead of turning a
  transient Hub issue into a blank dashboard.

Transfer to our own Gemma and Qwen production work:

1. **Readiness warm pack manager.** Treat graph captures, prefix caches,
   route atlases, expert descriptor tables, and quality canary prompts as
   explicit warm artifacts built before readiness. Record cold-start and warm
   steady-state separately.
2. **Single-flight warm artifact refresh.** If many requests need the same
   graph/prefix/route pack, one worker builds it while others await or use the
   last good artifact. This avoids a thundering-herd compile/cache miss.
3. **Content-addressed artifact cache.** Key route digests, generated kernels,
   prompt-prefix caches, and quality baselines by model revision, engine build,
   quantization, shape, and source hash. Stale entries should be invalidated
   deterministically rather than by timestamp guesses.
4. **Bounded fanout for production maintenance.** Limit concurrent background
   graph captures, quality probes, and benchmark fetches so observability or
   warmup cannot steal the very latency budget being measured.
5. **Stale-good fallback lane.** For dashboards, manifests, and quality
   metadata, serve the last validated artifact when refresh fails. For model
   serving this means falling back to the exact reference lane or previous
   validated graph, never to an unproven fast path.

This does not change the current Qwen3.6 optimization target. It strengthens
the production discipline around any future fast lane: warmed artifacts should
be explicit, bounded, content-addressed, and quality-gated.
