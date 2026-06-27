# llama.cpp Gemma4 Router Post-Scale Patch

Date: 2026-06-27

Source worktree:

```text
/home/steve/src/llama.cpp-gemma-record-stack
```

Outcome:

- full validation:
  `data/gemma4-q8-gpu2-routerpost-rms-ub832-fullrepeat-20260627T0758Z/summary.json`;
- canary: `6144/6144` rows passed;
- fresh row0: `104.19915421673585 tok/s`;
- current record at time of test: `104.30919255569083 tok/s`;
- decision: loss, no LocalMaxxing submission.

## Patch Intent

Avoid a wide router input scale by moving Gemma4's scalar router normalization
factor from the router input to the router logits.

The original graph shape:

```text
tmp = RMS(attn_out)
tmp = scale(tmp, 1 / sqrt(n_embd))
tmp = tmp * ffn_gate_inp_s
logits = ffn_gate_inp @ tmp
```

The experiment under `LLAMA_GEMMA4_MOE_ROUTER_POST_SCALE=1`:

```text
tmp = RMS(attn_out)
tmp = tmp * ffn_gate_inp_s
logits = ffn_gate_inp @ tmp
logits = scale(logits, 1 / sqrt(n_embd))
```

This is algebraically equivalent for an unbiased linear router projection. It
is not guaranteed bit-exact on every backend because moving a scalar across a
quantized SYCL matmul can perturb values near a router tie.

## Focused Diff

```diff
+static bool llama_gemma4_moe_router_post_scale_enabled() {
+    const char * env = std::getenv("LLAMA_GEMMA4_MOE_ROUTER_POST_SCALE");
+    if (env == nullptr || env[0] == '\0') {
+        return false;
+    }
+
+    return strcmp(env, "1") == 0 || strcmp(env, "true") == 0 ||
+        strcmp(env, "TRUE") == 0 || strcmp(env, "yes") == 0 ||
+        strcmp(env, "on") == 0;
+}
+
             // custom MoE logits calculation (router operates on attn_out, not cur)
-            ggml_tensor * tmp = ggml_rms_norm(ctx0, attn_out, hparams.f_norm_rms_eps);
-            tmp = ggml_scale(ctx0, tmp, 1.0f / sqrtf((float) n_embd));
+            const bool router_post_scale =
+                llama_gemma4_moe_router_post_scale_enabled();
+            ggml_tensor * tmp = reuse_attn_rms ?
+                    attn_out_rms :
+                    ggml_rms_norm(ctx0, attn_out, hparams.f_norm_rms_eps);
+            const float router_scale = 1.0f / sqrtf((float) n_embd);
+            if (!router_post_scale) {
+                tmp = ggml_scale(ctx0, tmp, router_scale);
+            }
             tmp = ggml_mul(ctx0, tmp, model.layers[il].ffn_gate_inp_s);
             ggml_tensor * logits = build_lora_mm(model.layers[il].ffn_gate_inp, tmp); // [n_expert, n_tokens]
+            if (router_post_scale) {
+                logits = ggml_scale(ctx0, logits, router_scale);
+            }
             cb(logits, "ffn_moe_logits", il);
```

## Harness Capture

The results harness records the flag in:

- `scripts/run-gemma4-26b-first-baseline.sh`;
- `scripts/run-gemma4-26b-llamacpp-replica.sh`.

This is useful even for a failed experiment because future agents can identify
whether the default-off flag was involved in a run identity.

## Decision

Keep as a rejected/default-off experiment. Do not promote as a record or a
recommended recipe.

The patch was quality-clean but did not improve the full fresh-response metric.
The promising screen result (`104.81345372517579 tok/s`) collapsed to
`104.19915421673585 tok/s` on full validation.

