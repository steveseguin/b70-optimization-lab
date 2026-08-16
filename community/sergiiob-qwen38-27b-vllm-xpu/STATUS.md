# SergioB Qwen3.8 27B vLLM XPU recipe status

- **Evidence level:** `community-reported`
- **Patch review status:** source-read; syntax checked; safetensors headers
  range-read; patchers not executed
- **Reference-lab model run:** no
- **Captured:** 2026-08-15T23:42:27-04:00
- **Cookbook commit:** `3beb704b5b86baed2a874a8cc96821116c97e080`
- **Model revision:** `9d189a60e4c0ad7f9f47cd94bfa393ca10b3924e`

This packet preserves a potentially useful single-B70 vLLM/XPU route for
Qwen3.8-27B. The reported speed numbers have not been reproduced in this lab
and must not be mixed into the promoted model board. Start with
[README.md](README.md) and review the unresolved identity questions before
running the copied files.

The copied Python patchers edit an installed vLLM package in place. They are
fail-closed on changed anchors, but they remain untrusted runtime mutations
until exercised in an isolated disposable container. Do not apply them to a
shared host environment.

The second URL supplied with this contribution, Burke Holland's
`build-the-urlist.md` gist, is unrelated to inference. Its exact captured
revision is recorded in `reported/source-manifest.json`; it contains a web-app
product specification and no Intel, B70, XPU, SYCL, vLLM, Qwen, kernel,
driver, model, or benchmark optimization.
