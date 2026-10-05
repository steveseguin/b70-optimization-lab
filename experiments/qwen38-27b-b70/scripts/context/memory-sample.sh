#!/usr/bin/env bash
# Client for MU_MODE=serve_run: where does the server's host memory go, and what does the first request of each kind add?
# Samples every server process (anonymous, file and shared resident memory from /proc/PID/status) when the server is
# ready, after a plain completion, after a chat completion and after a chat completion with top-20 scores.
# Uses curl and awk only, so the sampler itself costs nothing. Needs BASE_URL, MODEL_NAME, OUT_DIR.
set -u
sample() {
  { echo "== $1 $(date +%T) available_kb=$(awk '/MemAvailable/{print $2}' /proc/meminfo) gpuactive_kb=$(awk '/GPUActive/{print $2}' /proc/meminfo)"
    for p in $(ps -eo pid,rss --sort=-rss | awk 'NR>1 && $2>200000 {print $1}'); do
      echo "$p $(awk '/^(RssAnon|RssFile|RssShmem|VmSwap|VmLck):/{printf "%s%s ", $1, $2}' /proc/$p/status 2>/dev/null) $(tr '\0' ' ' </proc/$p/cmdline 2>/dev/null | cut -c1-70)"
    done; } | tee -a "$OUT_DIR/memory-sample.txt"
}
ask() { curl -s -m 600 "$BASE_URL/v1/$1" -H 'Content-Type: application/json' -d "$2" | head -c 300; echo; }
sample ready
sleep 15; sample ready+15s
ask completions "{\"model\":\"$MODEL_NAME\",\"prompt\":\"The capital of France is\",\"max_tokens\":8,\"temperature\":0}"
sleep 5; sample after-completion
ask chat/completions "{\"model\":\"$MODEL_NAME\",\"messages\":[{\"role\":\"user\",\"content\":\"Is 7 greater than 3? Answer yes or no.\"}],\"max_tokens\":4,\"temperature\":0,\"chat_template_kwargs\":{\"enable_thinking\":false}}"
sleep 5; sample after-chat
ask chat/completions "{\"model\":\"$MODEL_NAME\",\"messages\":[{\"role\":\"user\",\"content\":\"Is 7 greater than 3? Answer yes or no.\"}],\"max_tokens\":1,\"temperature\":0,\"logprobs\":true,\"top_logprobs\":20,\"chat_template_kwargs\":{\"enable_thinking\":false}}"
sleep 5; sample after-chat-logprobs
sleep 20; sample settled
