# SergioB Qwen3.8 27B vLLM XPU recipe status

- **Evidence level:** `B70-tested` for target-only and MTP1/2/4 at 8K;
  `community-reported` for 131K, power, contributor prompts, and broader
  quality claims
- **Patch review status:** source-read; syntax checked; safetensors headers
  range-read; both patchers applied and passed a second-run idempotency check
  inside the pinned image without devices; MTP4 patch-off/on performance,
  acceptance, memory, and output parity confirm the nightly patch is redundant
  for the pinned model at 8K; the 131K boundary patch remains untested
- **Reference-lab model run:** yes; target-only eager/graph and native
  MTP1/2/4 on one ASRock B70, exact model/image, p512/g128 n=5
- **Captured:** 2026-08-15T23:42:27-04:00
- **Cookbook commit:** `3beb704b5b86baed2a874a8cc96821116c97e080`
- **Model revision:** `9d189a60e4c0ad7f9f47cd94bfa393ca10b3924e`

This packet preserves a useful single-B70 vLLM/XPU route for Qwen3.8-27B. The
target-only XPU-graph idea is locally verified at 33.6903 tok/s versus 25.4184
eager. MTP1/2/4 reached 54.1758, 68.2322, and 83.7019 tok/s; the MTP4 result
matches the contributor's 83.7 claim. All four optimized modes retained the
same five greedy visible-output hashes as eager. Long-context, power,
contributor-prompt identity, runtime draft dtype, and broad semantic quality
remain unresolved and must not be mixed into the promoted model board. Start with
[README.md](README.md) and review the unresolved identity questions before
running the copied files.

The copied Python patchers edit an installed vLLM package in place. They are
fail-closed on changed anchors and passed an isolated apply/idempotency check
against the pinned image. This proves patch compatibility, not model
correctness or performance. Do not apply them to a shared host environment.

Local artifact and patch evidence is recorded in
[`validation/2026-08-16-local-artifact-and-patch-audit.md`](validation/2026-08-16-local-artifact-and-patch-audit.md).
The local GPU result and its limitations are recorded in
[`validation/2026-08-16-local-target-only-graph-validation.md`](validation/2026-08-16-local-target-only-graph-validation.md).
The native-MTP matrix is recorded in
[`validation/2026-08-16-local-mtp-matrix-validation.md`](validation/2026-08-16-local-mtp-matrix-validation.md).

The second URL supplied with this contribution, Burke Holland's
`build-the-urlist.md` gist, is unrelated to inference. Its exact captured
revision is recorded in `reported/source-manifest.json`; it contains a web-app
product specification and no Intel, B70, XPU, SYCL, vLLM, Qwen, kernel,
driver, model, or benchmark optimization.
