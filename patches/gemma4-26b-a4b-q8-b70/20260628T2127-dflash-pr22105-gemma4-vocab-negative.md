# DFlash PR 22105 Gemma 4 conversion/runtime screen

Date: 2026-06-28

Status: **negative for throughput; keep only as a feasibility artifact**.

## Context

Goal was to test whether DFlash can crack the reliable `>100 tok/s` strict
fresh-response target for Gemma 4 26B A4B Q8 on one Intel B70.

References:

- Source tree: `/home/steve/src/llama.cpp-dflash-gemma4`
- Upstream branch: llama.cpp PR 22105, commit
  `e8f1015ee7177fddc1f99c89772bef1b2640e375`
- DFlash HF draft: `z-lab/gemma-4-26B-A4B-it-DFlash`
- Target model: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`

## Build/conversion

The PR branch builds with the same Intel SYCL compiler stack as the record
build:

```bash
source /opt/intel/oneapi/setvars.sh
cmake -S /home/steve/src/llama.cpp-dflash-gemma4 \
  -B /home/steve/src/llama.cpp-dflash-gemma4/build-sycl-b70-dflash-pr22105 \
  -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_C_COMPILER=/opt/intel/oneapi/compiler/2026.0/bin/icx \
  -DCMAKE_CXX_COMPILER=/opt/intel/oneapi/compiler/2026.0/bin/icpx \
  -DGGML_SYCL=ON -DGGML_SYCL_F16=ON -DGGML_SYCL_TARGET=INTEL \
  -DCMAKE_CXX_FLAGS='-DGGML_SYCL_REORDER_Q8_0_VDR_MMVQ=2'
cmake --build /home/steve/src/llama.cpp-dflash-gemma4/build-sycl-b70-dflash-pr22105 \
  --target llama-server -j "$(nproc)"
```

The draft model converts after a small isolated converter patch. The PR's
`DFlashModel` inherits the Qwen vocab path; Gemma 4 needs the existing Gemma 4
vocab writer when `--target-model-dir` points at a Gemma 4 tokenizer directory.

Patch applied only in `/home/steve/src/llama.cpp-dflash-gemma4`:

```diff
diff --git a/conversion/qwen.py b/conversion/qwen.py
index 81f450e40..da2d5677e 100644
--- a/conversion/qwen.py
+++ b/conversion/qwen.py
@@ -1,5 +1,6 @@
 from __future__ import annotations
 
+import json
 from typing import Any, Callable, Iterable, TYPE_CHECKING
 
 import torch
@@ -638,6 +639,40 @@ class DFlashModel(Qwen3Model):
                 "Please provide the path to the target model directory containing the tokenizer."
             )
         logger.info(f"DFlash: Using tokenizer from target model: {self.target_model_dir}")
+        with open(self.target_model_dir / "config.json", encoding="utf-8") as f:
+            target_hparams = json.load(f)
+        if target_hparams.get("model_type") == "gemma4":
+            vocab = gguf.LlamaHfVocab(self.target_model_dir)
+            tokens = []
+            scores = []
+            toktypes = []
+            visible_tokens = {"<|channel>", "<channel|>", "<|tool_call>",
+                              "<tool_call|>", "<|tool_response>",
+                              "<tool_response|>", "<|\"|>"}
+
+            for text, score, toktype in vocab.all_tokens():
+                tokens.append(text)
+                scores.append(score)
+                text_str = text.decode()
+                if text_str in visible_tokens:
+                    toktypes.append(gguf.TokenType.USER_DEFINED)
+                    logger.info(f"Token '{text_str}' is set to USER_DEFINED")
+                else:
+                    toktypes.append(toktype)
+
+            assert len(tokens) == vocab.vocab_size
+
+            self.gguf_writer.add_tokenizer_model("gemma4")
+            self.gguf_writer.add_token_list(tokens)
+            self.gguf_writer.add_token_scores(scores)
+            self.gguf_writer.add_token_types(toktypes)
+
+            special_vocab = gguf.SpecialVocab(self.target_model_dir, load_merges=True)
+            special_vocab.add_to_gguf(self.gguf_writer)
+            self.gguf_writer.add_add_space_prefix(False)
+            self.gguf_writer.add_add_bos_token(True)
+            return
+
         original_dir = self.dir_model
         self.dir_model = self.target_model_dir
         super().set_vocab()
```

Converted draft:

`/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/DFlash/gemma-4-26B-A4B-it-DFlash-BF16.gguf`

## Runtime result

Screen command used strict fresh-response harness settings but was interrupted
early after the canary log showed the runtime was unusably slow:

- run dir:
  `data/gemma4-q8-gpu0-dflash-pr22105-bf16-screen128-20260628T212540Z/`
- server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-dflash-pr22105-bf16-screen128-20260628T212540Z.server.log`
- target: `UD-Q8_K_XL`
- draft: DFlash BF16 GGUF above
- `--spec-type draft-dflash --spec-draft-n-max 15`
- `cached_tokens=0` policy preserved; run was interrupted before final summary.

Representative early timings:

- task 0: eval `5477.97 ms / 11 tokens` = `2.01 tok/s`
- task 5: eval `4963.34 ms / 8 tokens` = `1.61 tok/s`
- task 10: eval `4305.04 ms / 3 tokens` = `0.70 tok/s`
- task 14: eval `4987.94 ms / 20 tokens` = `4.01 tok/s`

DFlash acceptance itself was not terrible in early positions:

- cumulative after 10 draft generations: `268 generated`, `85 accepted`
- mean accepted length around `5.7`
- first positions often accepted at high rates

But the DFlash generation path was far too expensive on this SYCL stack:

- cumulative DFlash generation duration after 18 generate calls:
  `2534.134 ms`, roughly `140 ms` per draft generation call.

## Decision

Do **not** promote or continue this lane on the current branch. It is much
slower than both no-spec (`~74 tok/s`) and the current MTP record stack
(`~98.34 tok/s`). The likely issue is not acceptance quality, but DFlash
draft-generation overhead on the current SYCL implementation.

Possible future revisit only if one of these changes:

- DFlash encoder/decoder path gets a SYCL-specific graph/fusion optimization;
- the draft can run far cheaper on the same GPU without target feature
  extraction overhead dominating;
- upstream PR lands with substantial runtime changes beyond this snapshot.

