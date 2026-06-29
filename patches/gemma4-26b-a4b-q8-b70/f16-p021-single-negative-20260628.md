Patch snapshot: F16 p021 small-ncols single-column extension (NEGATIVE)

Date: 2026-06-28 UTC
Source tree: /home/steve/src/llama.cpp-gemma-record-repro-c926
Flag tested: LLAMA_SYCL_F16_P021_SMALL_NCOLS=single

Outcome:
- Built successfully after fixing the helper assert.
- Strict gate passed with cached_tokens=0.
- Slower than the paired `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1` controls:
  - control GPU0: 94.895005243 tok/s
  - control GPU2: 96.200407664 tok/s
  - single GPU1: 94.229965892 tok/s
  - single GPU3: 92.275803780 tok/s
- Do not promote. The existing `=1` multi-column p021 path remains the record
  stack; `single` should stay disabled unless revisited with a new profile.

Focused patch excerpt against the local Gemma llama.cpp stack:

```diff
diff --git a/ggml/src/ggml-sycl/ggml-sycl.cpp b/ggml/src/ggml-sycl/ggml-sycl.cpp
--- a/ggml/src/ggml-sycl/ggml-sycl.cpp
+++ b/ggml/src/ggml-sycl/ggml-sycl.cpp
@@
 static bool ggml_sycl_f16_p021_small_ncols_enabled() {
     const char * env = std::getenv("LLAMA_SYCL_F16_P021_SMALL_NCOLS");
     return env && (std::strcmp(env, "1") == 0 ||
                    std::strcmp(env, "true") == 0 ||
                    std::strcmp(env, "TRUE") == 0 ||
                    std::strcmp(env, "yes") == 0 ||
-                   std::strcmp(env, "on") == 0);
+                   std::strcmp(env, "on") == 0 ||
+                   std::strcmp(env, "single") == 0);
 }
+
+static bool ggml_sycl_f16_p021_small_ncols_include_single() {
+    const char * env = std::getenv("LLAMA_SYCL_F16_P021_SMALL_NCOLS");
+    return env && (std::strcmp(env, "single") == 0);
+}
@@
-    GGML_ASSERT(src1->ne[1] > 1 && src1->ne[1] <= 8);
+    GGML_ASSERT(src1->ne[1] > (ggml_sycl_f16_p021_small_ncols_include_single() ? 0 : 1) &&
+                src1->ne[1] <= 8);
@@
-        src1->ne[1] > 1 && src1->ne[1] <= 8 &&
+        src1->ne[1] > (ggml_sycl_f16_p021_small_ncols_include_single() ? 0 : 1) &&
+        src1->ne[1] <= 8 &&
```

Result note:
`experiments/gemma4-26b-a4b-q8-b70/sweeps/20260628T0216-f16p021-single-negative.md`
