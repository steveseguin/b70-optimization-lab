# Qwen3.8 TP2/MTP1 no-repair D63 instrumentation-invalid failure

Date: 2026-08-31

D63 disabled the M=512 projection-repair hook and reproduced the TP2/MTP1
profile-run device-loss class. The target and drafter loaded, then both ranks
surfaced `UR_RESULT_ERROR_DEVICE_LOST` when the dummy sampler attempted to
allocate `SpecDecodeMetadata` after the asynchronous model forward. Xe logged
691 unsuccessful fault responses, 55 CCS engine-memory CAT errors, and two CCS
resets: one on each B70. No HTTP request was served and no performance or
quality value exists.

The frozen D63 receipt contract was not satisfied. The diagnostic image stores
its patched vLLM source under `/workspace/vllm`, but the generic launcher set
`PYTHONPATH=/instrument`. For the `/opt/venv/bin/vllm` console entry point,
that removed `/workspace/vllm` from module search and loaded the unpatched
`/opt/venv/lib/python3.12/site-packages/vllm` copy. This is proven by every
traceback path and by zero sampler-stage receipts. D63 is therefore formally
inconclusive for stage localization; its preregistered interpretation must not
be relaxed after seeing the outcome.

The projection repair was genuinely off, so the raw failure is useful
supporting evidence that the repair is not required to trigger the device-loss
class, but it is not accepted as the formal A/B classification because the
source-identity gate failed. After teardown, both B70s returned to normal and
passed independent deterministic matrix compute with no new kernel errors.

D64 corrects the import identity explicitly and adds finer decoder-layer
barriers under a new preregistration. D63 is not retried.

Raw evidence remains under
`/mnt/fast-ai/bench-results/qwen38-tp2-mtp1-no-projection-repair-startup-20260831-d63/`.
