# ctxkeeper 1.1.0: checked from the public release (2026-10-16 12:12-12:15)

- Downloaded every release file from `releases/download/ctxkeeper-v1.1.0/`; `sha256sum -c SHA256SUMS`: all OK.
- `pip install` of the wheel URL and of the source-archive URL into a fresh venv: `ctxkeeper --version` = 1.1.0 both ways.
- `docker build -t ... <source-archive URL>`: built; `--version` = 1.1.0.
- The demo through that image to Gemma 4 26B Q8 on llama.cpp (the LAN server, throughput profile: 4,096-token
  slots), `--recipe agent --budget 4000 --reply-reserve 700 --inplace-fit --log-calls`,
  `long_chat.py --tokens 16000 --max-tokens 400`: **4/4 in 60 s**, 9 cuts, 17 messages archived (`long_chat.out`,
  `proxy.log`).
