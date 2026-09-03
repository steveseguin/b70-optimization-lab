#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(git -C "${script_dir}" rev-parse --show-toplevel 2>/dev/null) || {
  printf 'ERROR: this verifier must run from a Git clone of b70-optimization-lab\n' >&2
  exit 2
}

required_files=(
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-pinned-mtp1-stack.sh
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/verify-image-contract.sh
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/Dockerfile.mtp1-serial-attention
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-mtp1-serial-attention-image.sh
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/Dockerfile.mtp1-rebuilt-gdn
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-mtp1-rebuilt-gdn-image.sh
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-mtp1-published-r55c-image.sh
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-pinned-mtp1-published-r55c-stack.sh
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/publication-manifest.json
  tools/validate-recipe-publication.py
  experiments/qwen38-27b-b70/patches/vllm-qwen38-xpu-serial-spec-flash-attn-r38-20260828.patch
  experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-qwen38-dynamic-active-width-serial-gdn-r35-20260828.patch
  experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-qwen38-gdn-split-serial-gates-r50-20260901.patch
  experiments/qwen38-27b-b70/patches/vllm-qwen38-fp8-draft-only-int4-lm-head-r62-20260901.patch
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/Dockerfile.draft-int4-r62
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-draft-int4-r62-image.sh
  experiments/qwen38-27b-b70/scripts/run-20260901-qwen38-fp8-mtp1-draft-int4-r62-server.sh
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-draft-int4-r62-prereg.json
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-draft-int4-r62-diagnostic-result.json
  experiments/qwen38-27b-b70/notes/2026-09-01-qwen38-fp8-mtp1-draft-int4-r62-diagnostic.md
  experiments/qwen38-27b-b70/data/2026-09-02-qwen38-fp8-mtp1-draft-int4-r62-cleanboot-r119-prereg.json
  experiments/qwen38-27b-b70/data/2026-09-02-qwen38-fp8-mtp1-draft-int4-r62-cleanboot-r119-result.json
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-fixed-k-w8a16-r139-image.sh
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/Dockerfile.fixed-k-w8a16-r139
  scripts/build-vllm-xpu-kernels-xpu-c-only.sh
  experiments/qwen38-27b-b70/patches/onednn-qwen38-w8a16-fixed-k-align16-r137a-20260902.patch
  experiments/qwen38-27b-b70/patches/onednn-qwen38-w8a16-c-default-align-r137b-20260902.patch
  experiments/qwen38-27b-b70/data/2026-09-02-qwen38-fp8-mtp1-fixed-k-serving-r139-prereg.json
  experiments/qwen38-27b-b70/data/2026-09-02-qwen38-fp8-mtp1-fixed-k-serving-r139-result.json
  experiments/qwen38-27b-b70/data/2026-09-02-qwen38-fp8-mtp1-fixed-k-regenerated-oracle-r147-prereg.json
  experiments/qwen38-27b-b70/data/2026-09-02-qwen38-fp8-mtp1-fixed-k-regenerated-oracle-r147-result.json
  experiments/qwen38-27b-b70/data/2026-09-02-qwen38-fp8-mtp0-fixed-k-probe-ladder-r147c-prereg.json
  experiments/qwen38-27b-b70/data/2026-09-02-qwen38-fp8-mtp0-fixed-k-probe-ladder-r147c-result.json
  experiments/qwen38-27b-b70/data/2026-09-02-qwen38-fp8-fixed-k-ladder-batched-2048-r148-prereg.json
  experiments/qwen38-27b-b70/data/2026-09-02-qwen38-fp8-fixed-k-ladder-batched-2048-r148-result.json
  experiments/qwen38-27b-b70/data/2026-09-02-qwen38-fp8-lm-head-chunk-rows-r149-prereg.json
  experiments/qwen38-27b-b70/data/2026-09-02-qwen38-fp8-lm-head-chunk-rows-r149-result.json
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-draft-int4-r63-concurrency-prereg.json
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-draft-int4-r63-control-prereg.json
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-draft-int4-r63-concurrency-result.json
  experiments/qwen38-27b-b70/notes/2026-09-01-qwen38-fp8-mtp1-draft-int4-r63-concurrency-negative.md
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-batch-invariant-r64-prereg.json
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-batch-invariant-r64-result.json
  experiments/qwen38-27b-b70/notes/2026-09-01-qwen38-fp8-mtp1-batch-invariant-r64-negative.md
  experiments/qwen38-27b-b70/scripts/run-20260901-qwen38-fp8-mtp1-batch-invariant-r64-server.sh
  experiments/qwen38-27b-b70/patches/vllm-qwen38-fp8-target-head-batch-invariant-r65-20260901.patch
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/Dockerfile.target-head-batch-invariant-r65
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-target-head-batch-invariant-r65-image.sh
  experiments/qwen38-27b-b70/scripts/run-20260901-qwen38-fp8-mtp1-target-head-batch-invariant-r65-server.sh
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-target-head-batch-invariant-r65-prereg.json
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-target-head-batch-invariant-r65-result.json
  experiments/qwen38-27b-b70/notes/2026-09-01-qwen38-fp8-mtp1-target-head-batch-invariant-r65-negative.md
  experiments/qwen38-27b-b70/patches/vllm-qwen38-fp8-selective-head-batch-repair-r66-20260901.patch
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/Dockerfile.selective-head-batch-repair-r66
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-selective-head-batch-repair-r66-image.sh
  experiments/qwen38-27b-b70/scripts/run-20260901-qwen38-fp8-mtp1-selective-head-batch-repair-r66-server.sh
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-selective-head-batch-repair-r66-prereg.json
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-selective-head-batch-repair-r66-result.json
  experiments/qwen38-27b-b70/notes/2026-09-01-qwen38-fp8-mtp1-selective-head-batch-repair-r66-invalid.md
  experiments/qwen38-27b-b70/scripts/run-20260901-qwen38-fp8-mtp1-selective-head-batch-repair-r67-server.sh
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-selective-head-batch-repair-r67-prereg.json
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-selective-head-batch-repair-r67-c2-result.json
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-selective-head-batch-repair-r67-full-prereg.json
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-selective-head-batch-repair-r67-full-result.json
  experiments/qwen38-27b-b70/notes/2026-09-01-qwen38-fp8-mtp1-selective-head-batch-repair-r67-negative.md
  experiments/qwen38-27b-b70/patches/vllm-qwen38-fp8-global-head-batch-repair-r68-20260901.patch
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/Dockerfile.global-head-batch-repair-r68
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-global-head-batch-repair-r68-image.sh
  experiments/qwen38-27b-b70/scripts/run-20260901-qwen38-fp8-mtp1-global-head-batch-repair-r68-server.sh
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-global-head-batch-repair-r68-prereg.json
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-global-head-batch-repair-r68-result.json
  experiments/qwen38-27b-b70/notes/2026-09-01-qwen38-fp8-mtp1-global-head-batch-repair-r68-negative.md
  experiments/qwen38-27b-b70/patches/vllm-qwen38-fp8-global-top-token-repair-r69-20260901.patch
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/Dockerfile.global-top-token-repair-r69
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-global-top-token-repair-r69-image.sh
  experiments/qwen38-27b-b70/scripts/run-20260901-qwen38-fp8-mtp1-global-top-token-repair-r69-server.sh
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-global-top-token-repair-r69-prereg.json
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-global-top-token-repair-r69-result.json
  experiments/qwen38-27b-b70/notes/2026-09-01-qwen38-fp8-mtp1-global-top-token-repair-r69-negative.md
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-global-top-token-repair-force-r70-prereg.json
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-global-top-token-repair-force-r70-result.json
  experiments/qwen38-27b-b70/notes/2026-09-01-qwen38-fp8-mtp1-global-top-token-repair-force-r70-negative.md
  experiments/qwen38-27b-b70/patches/vllm-qwen38-fp8-global-exact-head-repair-r71-20260901.patch
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/Dockerfile.global-exact-head-repair-r71
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-global-exact-head-repair-r71-image.sh
  experiments/qwen38-27b-b70/scripts/run-20260901-qwen38-fp8-mtp1-global-exact-head-repair-r71-server.sh
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-global-exact-head-repair-r71-prereg.json
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-global-exact-head-repair-r71-result.json
  experiments/qwen38-27b-b70/notes/2026-09-01-qwen38-fp8-mtp1-global-exact-head-repair-r71-negative.md
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-global-exact-head-repair-force-r72-prereg.json
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-global-exact-head-repair-force-r72-result.json
  experiments/qwen38-27b-b70/notes/2026-09-01-qwen38-fp8-mtp1-global-exact-head-repair-force-r72-negative.md
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-cudagraph-boundary-trace-r73-prereg.json
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-cudagraph-boundary-trace-r73-result.json
  experiments/qwen38-27b-b70/notes/2026-09-01-qwen38-fp8-mtp1-cudagraph-boundary-trace-r73-invalid.md
  experiments/qwen38-27b-b70/scripts/qwen38-cudagraph-boundary-trace-sitecustomize-r73.py
  experiments/qwen38-27b-b70/scripts/run-20260901-qwen38-fp8-mtp1-cudagraph-boundary-trace-r73-server.sh
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/Dockerfile.cudagraph-boundary-trace-r73
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-cudagraph-boundary-trace-r73-image.sh
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-piecewise-boundary-trace-r74-prereg.json
  experiments/qwen38-27b-b70/scripts/qwen38-piecewise-boundary-trace-sitecustomize-r74.py
  experiments/qwen38-27b-b70/scripts/run-20260901-qwen38-fp8-mtp1-piecewise-boundary-trace-r74-server.sh
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/Dockerfile.piecewise-boundary-trace-r74
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-piecewise-boundary-trace-r74-image.sh
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-piecewise-selected-row-trace-r75-prereg.json
  experiments/qwen38-27b-b70/scripts/qwen38-piecewise-selected-row-trace-sitecustomize-r75.py
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/Dockerfile.piecewise-selected-row-trace-r75
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-piecewise-selected-row-trace-r75-image.sh
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-piecewise-selected-row1-trace-r76-prereg.json
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/Dockerfile.piecewise-selected-row1-trace-r76
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-piecewise-selected-row1-trace-r76-image.sh
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-piecewise-row-map-trace-r77-prereg.json
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-piecewise-boundary-localization-r77-result.json
  experiments/qwen38-27b-b70/notes/2026-09-01-qwen38-fp8-mtp1-piecewise-boundary-localization-r77.md
  experiments/qwen38-27b-b70/scripts/qwen38-piecewise-row-map-trace-sitecustomize-r77.py
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/Dockerfile.piecewise-row-map-trace-r77
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-piecewise-row-map-trace-r77-image.sh
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-c2-r72-oracle.json
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-gdn-c2-factorial-r78-prereg.json
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-gdn-c2-factorial-r78-conv-invalid.json
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-gdn-multi-request-split-r79-prereg.json
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-gdn-multi-request-split-r79-invalid.json
  experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-qwen38-gdn-multi-request-split-r79-20260901.patch
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/Dockerfile.gdn-multi-request-split-r79
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-gdn-multi-request-split-r79-image.sh
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-gdn-multi-request-followup-r80-prereg.json
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-gdn-multi-request-r80-result.json
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-gdn-combined-multi-request-r81-prereg.json
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-gdn-combined-multi-request-r81-result.json
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-gdn-metadata-trace-r82-prereg.json
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-gdn-metadata-trace-r82-result.json
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-gdn-evolving-metadata-r83-prereg.json
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-gdn-evolving-metadata-r83-result.json
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-gdn-c2-isolation-r84-prereg.json
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-gdn-c2-isolation-r84-result.json
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-gdn-state-input-r85-prereg.json
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-gdn-state-input-r85-result.json
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-gdn-prefill-input-r86-prereg.json
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-gdn-prefill-input-r86-result.json
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-qkvz-fixed-shape-r87-prereg.json
  experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-qwen38-gdn-multi-request-followup-r80-20260901.patch
  experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-qwen38-gdn-metadata-trace-r82-20260901.patch
  experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-qwen38-gdn-evolving-metadata-r83-20260901.patch
  experiments/qwen38-27b-b70/patches/vllm-qwen38-fp8-gdn-state-input-trace-r85-20260901.patch
  experiments/qwen38-27b-b70/patches/vllm-qwen38-fp8-gdn-prefill-input-trace-r86-20260901.patch
  experiments/qwen38-27b-b70/patches/vllm-qwen38-fp8-gdn-qkvz-fixed-shape-r87-20260901.patch
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/Dockerfile.gdn-multi-request-followup-r80
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-gdn-multi-request-followup-r80-image.sh
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/Dockerfile.gdn-metadata-trace-r82
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-gdn-metadata-trace-r82-image.sh
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/Dockerfile.gdn-evolving-metadata-r83
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-gdn-evolving-metadata-r83-image.sh
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/Dockerfile.gdn-state-input-trace-r85
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-gdn-state-input-trace-r85-image.sh
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/Dockerfile.gdn-prefill-input-trace-r86
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-gdn-prefill-input-trace-r86-image.sh
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/Dockerfile.gdn-qkvz-fixed-shape-r87
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-gdn-qkvz-fixed-shape-r87-image.sh
  experiments/qwen38-27b-b70/scripts/qwen38-det-gdn-c2-isolation-equivalence-r84.py
  scripts/bench-openai-concurrency-oracle.py
  scripts/test_bench_openai_concurrency_oracle.py
)

failed=0
for relative_path in "${required_files[@]}"; do
  if [[ ! -f "${repo_root}/${relative_path}" ]]; then
    printf 'MISSING %s\n' "${relative_path}" >&2
    failed=1
    continue
  fi
  if ! git -C "${repo_root}" ls-files --error-unmatch -- "${relative_path}" \
      >/dev/null 2>&1; then
    printf 'UNTRACKED %s\n' "${relative_path}" >&2
    failed=1
  fi
done

check_sha256() {
  local expected=$1
  local relative_path=$2
  local actual
  [[ -f "${repo_root}/${relative_path}" ]] || return
  actual=$(sha256sum "${repo_root}/${relative_path}" | awk '{print $1}')
  if [[ "${actual}" != "${expected}" ]]; then
    printf 'HASH MISMATCH %s\n  expected %s\n  actual   %s\n' \
      "${relative_path}" "${expected}" "${actual}" >&2
    failed=1
  fi
}

check_sha256 \
  127b4bc1dc9096e630698202bbc06f74ce4e87f603f3bdc64d09a0dfcc26fe30 \
  experiments/qwen38-27b-b70/patches/vllm-qwen38-xpu-serial-spec-flash-attn-r38-20260828.patch
check_sha256 \
  ad583014c92b8611a9e4e87868a3d492c3b6802ee557814b9ec794f147cd973e \
  experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-qwen38-dynamic-active-width-serial-gdn-r35-20260828.patch
check_sha256 \
  40ca8c3fc15fea1b7dda8d268761f0b1339eb821f5d8357b3da7600585fe750f \
  experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-qwen38-gdn-split-serial-gates-r50-20260901.patch
check_sha256 \
  594ee1a38fef377bba34db98f2fd7f51641ea9697b4bb622c9a54634b0bd87ab \
  experiments/qwen38-27b-b70/patches/vllm-qwen38-fp8-draft-only-int4-lm-head-r62-20260901.patch
check_sha256 \
  e87e8c0a2e9b6b6907ff079a6c4f807bbf3b3cf218f0a01064eb3a264bff361f \
  experiments/qwen38-27b-b70/patches/vllm-qwen38-fp8-target-head-batch-invariant-r65-20260901.patch
check_sha256 \
  53ca0cd22d50e91f78be7234e1e53ed2ee6ce461b2c8b0da03259544c3b0e5ea \
  experiments/qwen38-27b-b70/patches/vllm-qwen38-fp8-selective-head-batch-repair-r66-20260901.patch
check_sha256 \
  a8026bd83f1c3ac5671847561b8dca637cdb366a6cbb8a2257375527afc644be \
  experiments/qwen38-27b-b70/patches/vllm-qwen38-fp8-global-head-batch-repair-r68-20260901.patch
check_sha256 \
  902409d13c68ef0afc56cdce6385fcfb964061c218b2e5582de142f953a83d9b \
  experiments/qwen38-27b-b70/patches/vllm-qwen38-fp8-global-top-token-repair-r69-20260901.patch
check_sha256 \
  1796e4ecc6b10cd26f164ccc67f4bc4bf1f976388bfd05e948ab1753c083748a \
  experiments/qwen38-27b-b70/patches/vllm-qwen38-fp8-global-exact-head-repair-r71-20260901.patch
check_sha256 \
  beaaf5313d8f0447b8fea5a4c44795b4045794e0bcd1475cf3cd4b14c97a3e46 \
  experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-qwen38-gdn-multi-request-split-r79-20260901.patch
check_sha256 \
  44cd6c0b5f71a521ecca286c2f7d24a1df5405783daf664cf0d84bab83339212 \
  experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-qwen38-gdn-multi-request-followup-r80-20260901.patch
check_sha256 \
  acb887bef2b00f905dd7627ebe7084febe057890dd2a039c8db2dd17f03e6dd8 \
  experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-qwen38-gdn-metadata-trace-r82-20260901.patch
check_sha256 \
  db1495c911f7ca7b825e989b1a9f7cac15a8801c1b586e72c302bee00aeeac5c \
  experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-qwen38-gdn-evolving-metadata-r83-20260901.patch
check_sha256 \
  ceefa1f1160ae26b20707329a26d4526e3e3c1051e036aaa858b4c2c9785b644 \
  experiments/qwen38-27b-b70/patches/vllm-qwen38-fp8-gdn-state-input-trace-r85-20260901.patch
check_sha256 \
  5a42f301e3150feadcbf290c3eb26004442fecc11ec6946bd891961dc46d4aa0 \
  experiments/qwen38-27b-b70/patches/vllm-qwen38-fp8-gdn-prefill-input-trace-r86-20260901.patch
check_sha256 \
  c6384af1eaa45f0f49318f78c82a3f7485db19ebe3f5fe6f63c8f5bcafccf3a5 \
  experiments/qwen38-27b-b70/patches/vllm-qwen38-fp8-gdn-qkvz-fixed-shape-r87-20260901.patch

# Every chain-level path in the publication manifest is an executable hash
# contract. Keep this manifest-driven so a newly listed build input or evidence
# file cannot bypass missing, untracked, or digest checks.
manifest_path=${repo_root}/repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/publication-manifest.json
manifest_chain_files=0
if manifest_chain_bindings=$(python3 - "${manifest_path}" <<'PY'
import json
import re
import sys
from pathlib import PurePosixPath

manifest_path = sys.argv[1]
with open(manifest_path, encoding="utf-8") as handle:
    manifest = json.load(handle)

chains = manifest.get("chains")
if not isinstance(chains, dict):
    raise SystemExit("publication manifest chains must be an object")
missing = {"r62", "r139"} - set(chains)
if missing:
    raise SystemExit(f"publication manifest is missing chains: {sorted(missing)}")

sha256_re = re.compile(r"[0-9a-f]{64}")


def emit_bindings(node, label):
    if isinstance(node, dict):
        if "path" in node or "sha256" in node:
            path = node.get("path")
            digest = node.get("sha256")
            if not isinstance(path, str) or not path:
                raise SystemExit(f"{label} must bind a non-empty path")
            pure = PurePosixPath(path)
            if pure.is_absolute() or ".." in pure.parts:
                raise SystemExit(f"{label} path escapes the repository: {path}")
            if not isinstance(digest, str) or not sha256_re.fullmatch(digest):
                raise SystemExit(f"{label} must bind a lowercase SHA-256 digest")
            print(f"{path}\t{digest}")
        for key, value in node.items():
            emit_bindings(value, f"{label}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            emit_bindings(value, f"{label}[{index}]")


emit_bindings(chains, "chains")
PY
); then
  while IFS=$'\t' read -r relative_path expected; do
    [[ -n "${relative_path}" ]] || continue
    manifest_chain_files=$((manifest_chain_files + 1))
    if [[ ! -f "${repo_root}/${relative_path}" ]]; then
      printf 'MISSING %s\n' "${relative_path}" >&2
      failed=1
      continue
    fi
    if ! git -C "${repo_root}" ls-files --error-unmatch -- "${relative_path}" \
        >/dev/null 2>&1; then
      printf 'UNTRACKED %s\n' "${relative_path}" >&2
      failed=1
    fi
    check_sha256 "${expected}" "${relative_path}"
  done <<<"${manifest_chain_bindings}"
else
  printf 'INVALID manifest chain bindings\n' >&2
  failed=1
fi

if (( failed )); then
  printf '\nSOURCE CLOSURE FAILED\n' >&2
  printf 'Refresh the clone with: git pull --ff-only origin main\n' >&2
  exit 1
fi

# The publication manifest is the cross-check between the build scripts,
# tracked immutable inputs, release artifacts, and quality evidence. This
# prevents a stale hand-maintained hash above from blessing a build script that
# requires a different patch digest.
python3 "${repo_root}/tools/validate-recipe-publication.py" \
  "repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/publication-manifest.json"

printf 'PUBLIC SOURCE CLOSURE PASS\n'
printf 'commit=%s\n' "$(git -C "${repo_root}" rev-parse HEAD)"
printf 'tracked_files=%d\n' "${#required_files[@]}"
printf 'patch_hashes=pass\n'
printf 'manifest_chain_hashes=pass files=%d\n' "${manifest_chain_files}"
