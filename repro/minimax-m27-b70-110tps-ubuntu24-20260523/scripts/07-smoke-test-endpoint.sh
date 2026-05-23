#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
MODEL="${MODEL:-/mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround}"

curl -sS "$BASE_URL/health" -w "\nHTTP %{http_code}\n"
curl -sS "$BASE_URL/v1/models" | jq '.data[] | {id, max_model_len}'
curl -sS "$BASE_URL/v1/completions" \
  -H 'Content-Type: application/json' \
  -d "{
    \"model\": \"$MODEL\",
    \"prompt\": \"Return only the number 42:\\n\",
    \"max_tokens\": 16,
    \"temperature\": 0
  }" | jq '{model, text: .choices[0].text, usage}'

