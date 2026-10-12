#!/usr/bin/env bash
# One line every 30 s while the research server answers: time, then running totals from /metrics
# (requests, prompt tokens, tokens served from the prefix cache, generated tokens, seconds of prefill, decode, queue, time to first token).
OUT=$1
echo -e "time\trequests\tprompt_tokens\tcached_tokens\tgenerated_tokens\tprefill_s\tdecode_s\tqueue_s\tttft_s" >> "$OUT"
miss=0
while (( miss < 10 )); do
  m=$(curl -fsS -m 5 http://127.0.0.1:18196/metrics 2>/dev/null) || { miss=$((miss+1)); sleep 30; continue; }
  miss=0
  echo "$m" | awk -v t="$(date +%H:%M:%S)" '
    /^vllm:request_inference_time_seconds_count/ {r=$NF} /^vllm:prefix_cache_queries_total/ {q=$NF} /^vllm:prefix_cache_hits_total/ {h=$NF}
    /^vllm:generation_tokens_total/ {g=$NF} /^vllm:request_prefill_time_seconds_sum/ {p=$NF} /^vllm:request_decode_time_seconds_sum/ {d=$NF}
    /^vllm:request_queue_time_seconds_sum/ {qu=$NF} /^vllm:time_to_first_token_seconds_sum/ {tt=$NF}
    END {printf "%s\t%d\t%d\t%d\t%d\t%.1f\t%.1f\t%.1f\t%.1f\n", t, r, q, h, g, p, d, qu, tt}' >> "$OUT"
  sleep 30
done
