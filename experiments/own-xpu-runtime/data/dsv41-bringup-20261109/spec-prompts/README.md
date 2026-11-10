# Five varied prompts for the DSpark guessing runs

One prompt per class the lab's realistic suite asks for (code, prose, analysis, operations, documentation),
written for these runs on 2026-11-10 and used unchanged in every run since (`round17-e57..e61`). Each `<name>.txt` is
the user message; `<name>-ids.txt` is the model's chat-formatted prompt (DeepSeek V4.1 Flash chat template,
`data/dsv41-tokenizer/`), one token id per line, made with

```bash
~/.venvs/vllm-xpu/bin/python experiments/own-xpu-runtime/engine/tools/mk_chat_ids.py \
  experiments/own-xpu-runtime/data/dsv41-tokenizer <name>.txt <name>-ids.txt
```

| prompt | ids | what it asks for |
| --- | --- | --- |
| code | 82 | a Python `merge_intervals` function with docstring, type hints and three unit tests |
| prose | 62 | a 250-word short story |
| analysis | 113 | a bakery pricing decision, worked through |
| ops | 74 | a checklist for diagnosing a slow Linux server |
| docs | 78 | a README "Configuration" section for a made-up tool |

Every answer is the target model's greedy text up to its end-of-sentence token or 512 tokens; a guessing run's
answer is compared with the plain run's (`OWN_VERIFY_REF`) and must be the same token for token.
