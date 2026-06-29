# Top1 Epilogue Node-Profile Excerpt

Diagnostic only. This run was launched with:

```bash
GGML_SYCL_NODE_PROFILE=1
GGML_SYCL_NODE_PROFILE_DETAIL=1
LLAMA_SERVER_SPEC_PROFILE=1
LLAMA_SPEC_VERIFY_REGULAR_MMVQ_TOP1_EPILOGUE=1
LLAMA_SYCL_MUL_MAT_TOP1_EPILOGUE=1
GPU_INDEX=0
PORT=18432
MAX_TOKENS=128
CANARY_REPEATS=16
LABEL=gemma4-q8-gpu0-top1epilogue-on-nodeprofile-20260629T1455Z
```

The benchmark completed the canary and fixed realistic suite, but the parent
script exited before writing `summary.json` because the script was edited while
it was still running. Use `realistic-suite.json` and this profile excerpt for
diagnostic evidence.

Realistic-suite summary:

- cache policy: all 12 prompts had `cached_tokens=0`;
- primary median tokens 1-100 after TTFT: `69.29316575774916 tok/s`;
- p10: `63.55603437983125`;
- mean: `69.15937473191518`;
- node profiling overhead makes this non-comparable to record throughput.

Key profile lines from `server.stdout.log`:

```text
1.01.368.086 W sycl node profile:  1 total_ms=982.173 calls=741 avg_ms=1.325 MUL_MAT_ARGMAX:spec_verify_regular_mmvq_top1_epilogue_token_rows
1.01.368.088 W sycl node profile:  2 total_ms=528.637 calls=895 avg_ms=0.591 MUL_MAT_ID:ffn_moe_gate_up-29
1.01.368.110 W sycl node profile: 29 total_ms=302.905 calls=736 avg_ms=0.412 MUL_MAT_ARGMAX:mtp_direct_argmax_unroll_token_0
1.01.638.955 I srv  print_spec_p: server spec profile: draft_ms=3748.642 calls=900 draft_tokens=2214 avg=4.165 ms
1.01.638.956 I srv  print_spec_p: server spec profile: target_decode_ms=38779.007 calls=900 tokens=6321 avg=43.088 ms avg_token=6.135 ms
```

Conclusion: the new top1 epilogue graph path was active, but it remained the
largest node at ~`1.325 ms/call`. That explains the strict128 loss versus the
paired control and closes the activation ambiguity.
