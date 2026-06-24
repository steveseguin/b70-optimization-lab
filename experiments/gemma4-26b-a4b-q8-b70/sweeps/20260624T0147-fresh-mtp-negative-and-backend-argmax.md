# 2026-06-24T0147: fresh MTP rechecks and backend-argmax follow-up

Model/lane:

- model: Gemma 4 26B A4B IT, Unsloth GGUF Q8_K_XL
- source: `/home/steve/src/llama.cpp-latest-gemma`, commit reported as `c926ad098`
- server binary:
  `/home/steve/src/llama.cpp-latest-gemma/build-sycl-b70-aot-bmg-g31/bin/llama-server`
- quality lane: Q8 weights, f16 target KV, f16 draft KV
- validity rule: headline throughput must use fresh-response first request
  (`p512o512.json.rows[0].tok_s_after_ttft`) unless the method is known not to
  learn repeated continuations. For n-gram/history methods, do not use warmed
  repeated-prompt means as fresh throughput.

Current promoted fresh single-GPU record remains:

- `data/gemma4-q8-gpu0-mtp-n7-c926-fastargmax-cpucleanup-vmm0-ub512-poll100-full-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-20260623T222838Z/`
- canary: 384/384
- fresh first request after TTFT: 92.397 tok/s
- supporting repeat mean after TTFT: 92.767 tok/s (not the headline fresh
  number)
- `cached_tokens=0` for all benchmark rows

## Four-GPU fresh sweep

All runs below used:

- `--cache-ram 0`
- `--ctx-checkpoints 0`
- `BENCH_PROMPT_MODE=filled-long`
- `PROMPT_TOKENS=512`, `MAX_TOKENS=512`
- no n-gram/history speculation
- `cached_tokens=0`
- canary 256/256

| label | change | fresh first tok/s | mean tok/s | wall mean | result |
| --- | --- | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-mtp-n7-cleanrebuild-confirm64-ctx8192ub512poll100-20260624TfreshA` | clean rebuild baseline confirmation | 91.464 | 91.501 | 80.510 | valid, below record |
| `gemma4-q8-gpu1-mtp-n7-verifyargmax-ctx8192ub512poll100-20260624TfreshA` | `LLAMA_SPEC_VERIFY_GREEDY_ARGMAX=1` | 91.267 | 91.353 | 80.365 | valid, below record |
| `gemma4-q8-gpu2-mtp-n7-poll150-ctx8192ub512-20260624TfreshA` | `POLL=150` | 91.092 | 91.053 | 80.102 | valid, below record |
| `gemma4-q8-gpu3-mtp-n7-threads8-ctx8192ub512poll100-20260624TfreshA` | `THREADS=8` | 91.675 | 91.732 | 80.734 | valid, below record |

Interpretation:

- Small runtime knobs are not moving the record.
- Target verifier greedy argmax did not help; target decode and draft work still
  dominate.
- Baseline profile confirms the large cost is serial MTP draft decode:
  `draft_decode_ms ~= 6226 ms` over the 2-repeat run, versus
  `fast_scan_ms ~= 401 ms`. Removing draft CPU vocab scans can only be a modest
  win unless it also improves graph reuse or scheduling.

## Backend draft argmax code experiment

Patch under test:

- source file: `/home/steve/src/llama.cpp-latest-gemma/common/speculative.cpp`
- new env: `LLAMA_MTP_DRAFT_BACKEND_ARGMAX=1`
- harness identity updates:
  - `scripts/run-gemma4-26b-mtp-candidate.sh`
  - `scripts/run-gemma4-26b-first-baseline.sh`
  - `scripts/run-gemma4-26b-llamacpp-replica.sh`

Idea:

- When draft backend sampling is enabled, attach a backend greedy sampler to the
  draft context.
- In the MTP draft loop, read `llama_get_sampled_token_ith(ctx_dft, idx)` and
  skip the current CPU-side `llama_get_logits_ith()` full-vocab argmax scan.
- Target verification remains unchanged and exact, so final output should remain
  valid if the sampled draft token is wrong.

Risk/expectation:

- This is not expected to reach the >150 tok/s target by itself because serial
  draft decode remains dominant.
- It may still recover the ~0.4s benchmark cost attributed to CPU vocab scans
  and produce a small valid fresh record.
- Current fast-argmax lane already sets draft candidate probability to 1.0, so
  `p_min=0.12` is already effectively bypassed in that lane; backend argmax is
  comparable on that point.

Result:

- Rejected. Backend argmax removed the CPU-side draft vocab scans, but it did
  not improve fresh throughput. Profiles showed `vocab_scanned=0`,
  `fast_scan_ms=0`, and `fast_logits_ms=0`, so the patch did what it was meant
  to do. Throughput still fell because the dominant cost is serial draft
  `llama_decode()` work, not CPU argmax scanning.

Patch artifact:

- `patches/gemma4-llamacpp-mtp-record-stack-plus-backendargmax-negative-20260624.patch`

Fresh validation runs, all with `cached_tokens=0` and 256/256 chat canary:

| label | change | fresh first tok/s | mean tok/s | wall mean | result |
| --- | --- | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-mtp-n7-backendargmax-ctx8192ub512poll100-20260624TfreshB` | backend draft argmax | 90.850 | 90.893 | 80.081 | valid, below record |
| `gemma4-q8-gpu1-mtp-n7-backendargmax-verifyargmax-ctx8192ub512poll100-20260624TfreshB` | backend draft argmax + target verifier argmax | 91.154 | 91.002 | 80.140 | valid, below record |
| `gemma4-q8-gpu2-mtp-n7-backendargmax-pmin0-ctx8192ub512poll100-20260624TfreshB` | backend draft argmax, `p_min=0` | 91.332 | 91.236 | 80.329 | valid, below record |
| `gemma4-q8-gpu3-mtp-n8-backendargmax-ctx8192ub512poll100-20260624TfreshB` | backend draft argmax, `n_max=8` | 62.067 | 62.067 | 56.882 | valid, severe regression |

Conclusion:

- Do not promote backend draft argmax. It is a useful negative control proving
  the next optimization must reduce or restructure the serial MTP draft decode
  itself. Sampler-side micro-optimizations are exhausted for the `>150 tok/s`
  target.
- Keep the patch artifact and result directories for future reference, but do
  not submit these runs to LocalMaxxing because they do not beat the current
  fresh-response record.
