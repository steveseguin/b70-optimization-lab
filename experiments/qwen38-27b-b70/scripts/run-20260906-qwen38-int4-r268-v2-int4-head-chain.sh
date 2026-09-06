#!/usr/bin/env bash
# R268 chain: after pid $1 exits, smoke the R266 image (V2 loader draft-only INT4 head) under the V2 runner, with and without
# async scheduling.
S=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
[[ -n "${1:-}" ]] && while kill -0 "$1" 2>/dev/null; do sleep 30; done
IMG=neural-download/vllm-openai-xpu:qwen38-int4-v2-draft-int4-head-r266 ASYNC=1 V2=1 DRAFT_HEAD_INT4=1 RUN=r268a "$S/run-20260906-qwen38-int4-r267-async-scheduling-smoke.sh"
IMG=neural-download/vllm-openai-xpu:qwen38-int4-v2-draft-int4-head-r266 ASYNC= V2=1 DRAFT_HEAD_INT4=1 RUN=r268b "$S/run-20260906-qwen38-int4-r267-async-scheduling-smoke.sh"
