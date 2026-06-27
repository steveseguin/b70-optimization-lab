# llama.cpp Gemma4 MoE RMS Reuse Patch

Date: 2026-06-27

Source worktree:

```text
/home/steve/src/llama.cpp-gemma-record-stack
```

Result:

- full validation:
  `data/gemma4-q8-gpu0-rmsreuse-ub768-nmin3-pmin010-fullrepeat-20260627T070421Z/summary.json`;
- fresh row0: `104.30919255569083 tok/s`;
- support mean: `103.93445004566178 tok/s`;
- canary: `6144/6144` rows;
- LocalMaxxing: `cmqw1tgzx0366qr01g4lkv7f1`.

This is a tiny row0 micro-record over `104.22626983476746 tok/s`, not a
material breakthrough toward `>150 tok/s`.

## Patch Intent

Gemma4 MoE layers consumed the same `attn_out` through three independent RMSNorm
nodes:

- shared MLP norm via `ffn_norm`;
- routed expert FFN norm via `ffn_pre_norm_2`;
- router norm before `ffn_gate_inp`.

The patch adds a default-off env flag:

```text
LLAMA_GEMMA4_MOE_REUSE_ATTN_RMS=1
```

When enabled, the graph computes one unweighted `ggml_rms_norm(attn_out, eps)`
and reuses it for the three branches. The router still applies the existing
`1/sqrt(n_embd)` scale before the router matmul; no router scaling was moved
across the linear projection.

## Focused Diff

```diff
+static bool llama_gemma4_moe_reuse_attn_rms_enabled() {
+    const char * env = std::getenv("LLAMA_GEMMA4_MOE_REUSE_ATTN_RMS");
+    if (env == nullptr || env[0] == '\0') {
+        return false;
+    }
+
+    return strcmp(env, "1") == 0 || strcmp(env, "true") == 0 ||
+        strcmp(env, "TRUE") == 0 || strcmp(env, "yes") == 0 ||
+        strcmp(env, "on") == 0;
+}
+
         if (is_moe_layer) {
+            const bool reuse_attn_rms =
+                llama_gemma4_moe_reuse_attn_rms_enabled();
+            ggml_tensor * attn_out_rms = nullptr;
+            if (reuse_attn_rms) {
+                attn_out_rms = ggml_rms_norm(ctx0, attn_out, hparams.f_norm_rms_eps);
+                cb(attn_out_rms, "ffn_attn_out_rms", il);
+            }
+
             // MLP (shared exp)
-            ggml_tensor * cur_mlp = build_norm(attn_out,
-                    model.layers[il].ffn_norm, nullptr,
-                    LLM_NORM_RMS, il);
+            ggml_tensor * cur_mlp = nullptr;
+            if (reuse_attn_rms) {
+                cur_mlp = ggml_mul(ctx0, attn_out_rms, model.layers[il].ffn_norm);
+            } else {
+                cur_mlp = build_norm(attn_out,
+                        model.layers[il].ffn_norm, nullptr,
+                        LLM_NORM_RMS, il);
+            }
             cb(cur_mlp, "ffn_norm_1", il);

             // Expert FFN
-            ggml_tensor * cur_moe = build_norm(attn_out,
-                    model.layers[il].ffn_pre_norm_2, nullptr,
-                    LLM_NORM_RMS, il);
+            ggml_tensor * cur_moe = nullptr;
+            if (reuse_attn_rms) {
+                cur_moe = ggml_mul(ctx0, attn_out_rms, model.layers[il].ffn_pre_norm_2);
+            } else {
+                cur_moe = build_norm(attn_out,
+                        model.layers[il].ffn_pre_norm_2, nullptr,
+                        LLM_NORM_RMS, il);
+            }
             cb(cur_moe, "ffn_norm_2", il);

             // custom MoE logits calculation (router operates on attn_out, not cur)
-            ggml_tensor * tmp = ggml_rms_norm(ctx0, attn_out, hparams.f_norm_rms_eps);
+            ggml_tensor * tmp = reuse_attn_rms ?
+                    attn_out_rms :
+                    ggml_rms_norm(ctx0, attn_out, hparams.f_norm_rms_eps);
             tmp = ggml_scale(ctx0, tmp, 1.0f / sqrtf((float) n_embd));
```

## Harness Capture

The results harness now captures `LLAMA_GEMMA4_MOE_REUSE_ATTN_RMS` in:

- `scripts/run-gemma4-26b-first-baseline.sh`;
- `scripts/run-gemma4-26b-llamacpp-replica.sh`.

This avoids silent env-only records.

## Follow-Up

The obvious next variant is moving the router scalar multiply from the wide
`[n_embd, n_tokens]` input to the post-router logits. That should preserve
linear math if no bias is present, but it is a distinct experiment and should
use a separate flag/result because this record intentionally avoided that
extra semantic risk.
