# Qwen3.8 repaired TP2/MTP0 D59 result

D59 failed before serving any request. Both ranks loaded the model, but the
2,048-token startup profile hit `UR_RESULT_ERROR_OUT_OF_RESOURCES` in rank 1's
AutoRound gate/up projection.

This was not a Docker/host OOM kill, GPU reset, storage fault, or strict-suite
failure. The profile shape was outside the repair branch and larger than the
bounded shapes used by prior local TP2 lanes. The hung readiness attempt was
stopped and cleaned up. D59r changes only `max-num-batched-tokens` to 256 and
adds fail-path container-log capture; all inference and quality gates remain.
