# Qwen3.8 GDN INT4 prefill pad D37 r1 image receipt — audit correction

The original invalid classification is withdrawn. The import smoke ran from
the image's `/workspace/vllm` working directory and therefore resolved the
editable checkout. The actual vLLM server runs from a neutral directory and
imports `/opt/venv/lib/python3.12/site-packages/vllm`, which r1 did patch.
A neutral-directory import receipt confirms the runtime module contains the
new helper and M=512 constant. No model request was made before this correction.

Conversely, r2 patched only `/workspace/vllm`; the actual server runtime did
not contain its helper. D37r therefore measured the unmodified runtime, not the
candidate. D39 is the first valid r1 model gate.
