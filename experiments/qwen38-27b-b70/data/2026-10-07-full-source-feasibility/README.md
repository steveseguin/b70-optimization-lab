# Full-source prompt feasibility

This separate CPU calculation measures four prospective full-source prompts.
It does not implement or execute a model baseline, admit unused documents,
or change the frozen history study or its continuation rule.

Run with the existing local interpreter; no downloads are performed:

```sh
/mnt/fast-ai/venvs/clm/bin/python3 measure.py
```

The script requires `tokenizers` and `jinja2`. `--source` and `--tokenizer-dir`
can locate the same pinned files elsewhere; different bytes are rejected.
The output is always `receipt.json` in this directory. Reproduction overwrites
that receipt; paths and package versions describe the measuring environment.

The receipt includes all exact candidate requests, per-batch source hashes and
token counts, question hashes, serialized-message/request measurements, local
chat-template token counts, input/template/script hashes and declared limits.
It checks that candidate message hashes reproduce the prospective review.
Every batch and question is present verbatim; no annotations or oracle are read.

The 32,768-byte cap applies to serialized messages. HTTP-request bytes and
rendered model tokens are reported separately. Offline token counts are not
server usage measurements, and server context capacity is explicitly unverified.
Fit is not evidence of accuracy, cold cache, latency or intermediate-state quality.
All model-call, launch-admission and performance-claim fields remain zero/false.
