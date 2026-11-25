#!/bin/bash
# the reference's image path in its high-precision mode: encoder dumps and 100 greedy tokens for card.png
cd /home/steve/inkling-work/vision
M=/mnt/fast-ai/llm-models/Inkling-2-Mini-GGUF/Inkling-2-Mini-UD-IQ4_XS.gguf
MP=/mnt/fast-ai/llm-models/Inkling-2-Mini-GGUF/mmproj-BF16.gguf
GGML_CPU_F32_ACT=1 REF_FA=0 REF_NO_REPACK=1 /usr/bin/time -v /home/steve/inkling-work/bin/ref_vision $M $MP card.png card-prompt.txt ref-card 100 \
  patch_embd embeddings pre_ln layer_inp_normed-0 Qcur_pos-0 Kcur_pos-0 kqv_out-0 attn_out-0 ffn_inp-0 ffn_out-0 layer_out-0 layer_out-11 layer_out-22 encoder_out pixel_shuffle projected \
  > ref-card.out 2> ref-card.err
echo done > refv.DONE
