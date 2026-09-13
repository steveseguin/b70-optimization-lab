# Qwen3.6-35B-A3B (GDN hybrid, MTP2): on-demand reproduction of the uniform-decode shape-alias corruption + fix confirmation on a second B70 host

## Classification

| Field | Value |
| --- | --- |
| Evidence level | `community-reported` |
| Patch review status | read and executed here (on the contributor's own B70 host, not the reference lab) |
| Tested in reference lab | no |
| Safe to merge as documentation | yes |
| Eligible for `repro/` or `results/` | no until `B70-tested` in the reference lab |

## Provenance

- Contributor: [`bosd`](https://github.com/bosd) (independent 2× Arc Pro B70 host; not the reference lab)
- Source PR or URL: this packet builds directly on [PR #45](https://github.com/steveseguin/b70-optimization-lab/pull/45) (`dominick253`, `community/dominick253-qwen38-27b-fp8-uniform-decode-alias/`)
- Commits: harness + patch authored for this packet; classifier fix is upstream, unchanged.
- Right-to-submit statement present: yes — I have the right to submit this material under the repository LICENSE; it contains no weights, secrets, tokens, or LAN identifiers.
- Third-party material and attribution:
  - vLLM (Apache-2.0): upstream issue [#53051](https://github.com/vllm-project/vllm/issues/53051) and fix PR [#53059](https://github.com/vllm-project/vllm/pull/53059) by `allenzz-dev` — credited; the applied guard is theirs.
  - `dominick253` PR #45 — the root-cause identification and the lane this corroborates.
  - Model `Qwen/Qwen3.6-35B-A3B` (GPTQ-Int4 MTP-preserved community requant); image `docker.io/vllm/vllm-openai-xpu`.

## Claim

On an independent 2× Arc Pro B70 host, dominick253's uniform-decode shape-alias
mechanism (#53051) reproduces **on demand** on a *different* GDN model —
Qwen3.6-35B-A3B (hybrid linear-attention/GDN) served under vLLM-XPU with MTP2 —
using a single greedy 3-token prompt: **18/30 (60%) degenerate `!!!!!` walls on
stock, 0/30 after the #53059 guard**, with no multi-hour dwell required.

## Contributor Environment

| Field | Value |
| --- | --- |
| GPU model / count / VRAM | 2× Intel Arc Pro B70, 32 GiB each; **one** card used for this service (`ZE_AFFINITY_MASK=2`) |
| OS / kernel | Fedora Linux 44 (Server Edition); `7.1.8-200.fc44.x86_64` |
| GPU driver (`i915` / `xe`) and version | `xe` |
| compute-runtime / level-zero | level-zero loader `1.28.2`, intel-opencl-icd `26.18.38308.1` (in image) |
| Engine / image and exact version | `docker.io/vllm/vllm-openai-xpu@sha256:2c427ef477da092eb6f2cdbbbd24950b5fa171565b916db69d4c7bb10e68ca97`, vLLM `0.26.1rc1.dev457+gc810e5ee9`, torch `2.13.0+xpu` |
| Model repo and revision | `Qwen3.6-35B-A3B` GPTQ-Int4 MTP-preserved community requant; arch `Qwen3_5MoeForConditionalGeneration`, `config.json` `layer_types` = `linear_attention` (GDN) interleaved with `full_attention` every 4th layer (`full_attention_interval: 4`) — GDN-bearing |
| Quantization (weights / KV / activations) | weights GPTQ Int4 (`--quantization gptq`); `--dtype float16` |
| Command and environment variables | `vllm serve /model --quantization gptq --dtype float16 --max-model-len 40960 --gpu-memory-utilization 0.90 --port 8000 --max-num-seqs 32 --max-num-batched-tokens 8192 --no-enable-prefix-caching --served-model-name qwen36-35b-moe --language-model-only --enable-auto-tool-choice --tool-call-parser qwen3_coder --speculative-config '{"method":"mtp","num_speculative_tokens":2}'`; env `ZE_AFFINITY_MASK=2 VLLM_XPU_ENABLE_XPU_GRAPH=1 PYTORCH_ALLOC_CONF=expandable_segments:True`. Two pre-existing local MTP patches also load at entry (`patch_mtp_nightly.py`, `patch_mtp_boundary.py` — the latter handles a *different* GDN+spec edge: a partial final speculative group at the max-len boundary, not this prompt-length alias). |
| Prompt / output / context lengths, concurrency | greedy `temperature=0, seed=12345`, `max_tokens` 12–24; single-stream; **30 repeats per prompt shape**; prompts selected by exact token count via the server's `/tokenize` |
| Cache and speculation policy | `--no-enable-prefix-caching`; MTP method `mtp`, `num_speculative_tokens=2` → `uniform_decode_query_len = 3` |
| Metric definition, repeats, dispersion, TTFT | metric = **degenerate-output rate** over 30 greedy repeats; degenerate = an ≥8-char single-token run (`(.)\1{7,}`) or a ≥70% dominant non-alphanumeric char; TTFT not measured (correctness reproduction, not a throughput claim) |
| Logs / JSON / durable links | `reported/repro-results.md` (full stock/patched tables + raw run JSON); harness `reported/alias-harness.py`; fix `reported/patch_uniform_decode_alias.py` |

## What Was Actually Run Here

Everything in this packet ran on the **contributor's** 2× B70 host, *not* the
reference lab.

1. `reported/alias-harness.py` against the live unpatched service (MTP2): fired
   30 greedy `temperature=0` completions for each of four prompt shapes chosen
   by exact token count — the 3-token alias (`1+1`), 1-token (`Hi`), 2-token
   (`Hi.`), and a 13-token control.
2. Applied the #53059 classifier guard as an entry-time monkeypatch
   (`reported/patch_uniform_decode_alias.py`, same idiom as the lane's existing
   `patch_mtp_*.py`), restarted, and re-ran the identical harness.
3. Post-fix functional smokes (`17*23=391`, coherent generation) and confirmed
   spec-decode was still active from the server's own SpecDecoding metrics.
4. Ran PR #45's self-contained `test_is_uniform_decode_red_green.py` (stdlib +
   numpy) on CPU: RED PASS / GREEN PASS.

**Not run here:** the reference-lab R187/R50 sealed lane; the multi-hour
production soak; MTP depth > 2; the FP8 Qwen3.8-27B incident image itself
(this host reproduced the *mechanism* on a different GDN model, MTP2).

## Findings

**Confirmed (on this host):**

- The alias reproduces **deterministically and on demand** with a single fresh
  greedy 3-token prompt at MTP2, no dwell required: stock **18/30 (60%)**
  `!!!!!` walls at the 3-token alias point, versus **0/30** at the 2-token and
  13-token controls — corruption is isolated to `prompt_len == uniform_decode_query_len`.
- The 1-token prompt also degraded on stock (10/30, 33%) and cleared to 0/30
  post-fix, so that instability was the same path, not a separate short-prompt
  artifact.
- The #53059 guard eliminates it: **all four shapes 0/30 post-fix**, arithmetic
  correct, and the server's SpecDecoding metrics still report mean acceptance
  length 2.25–2.31 (~65% draft acceptance) — the guard rejects only aliased
  prefills; genuine uniform decodes keep the fast path.
- PR #45's CPU classifier test passes both directions.

**Hypothesis (not established here):**

- That this is the *same* mechanism as the contributor's multi-hour FP8
  Qwen3.8-27B incident. This host reproduced the mechanism on a *different*
  GDN model (Qwen3.6-35B-A3B) at MTP2 and a different image/vLLM version; the
  shared root cause (shape-only `_is_uniform_decode`) is identical, but a
  cross-image equivalence is inference, not measurement.

## Known Issues

- The reproduction is on Qwen3.6-35B-A3B / MTP2, not the FP8 Qwen3.8-27B / MTP1
  incident image; it corroborates the mechanism and the fix, not the specific
  incident's rate.
- Evidence is `community-reported`: a second-community-host B70 result, not a
  reference-lab run. Only the maintainer can raise it to `B70-tested`.
- The applied form is an entry-time monkeypatch of the site-packages module
  (matching this lane's existing `patch_mtp_*.py` deployment), not the R50
  bind-mount-over-editable-install shape; both target the live serve module.

## Open Questions For The Contributor

Answered by this packet, relative to #45's open questions:

- **#45 open-Q1 (does a short prompt trigger the alias on demand, or does the
  whole-graph line avoid it?):** on this host's PIECEWISE-default MTP2 setup, a
  3-token prompt triggers it deterministically (60%). Whether the reference
  lane's `splitting_ops=[]` whole-graph config avoids it remains for the lab.
- **Still open:** does `VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=0` (the lab's d5
  mitigation) also suppress this alias path? Not tested here.

## Disposition

A runnable, on-demand reproduction harness plus fix confirmation from an
independent B70 host, offered to raise #45's uniform-decode-alias finding from
"observed after 6–24 h dwell" to "reproduces in seconds with one 3-token
prompt." It stays `community-reported` until the maintainer runs it on the
reference lane; the harness is written to make that a single command.
