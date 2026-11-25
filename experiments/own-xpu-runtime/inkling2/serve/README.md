# Inkling-2-Mini LAN server

Inkling-2-Mini runs on one B70 card with our own engine. It speaks the OpenAI API on port 8001. Not installed as a
service yet: start it by hand (below) or install `systemd/inkling-server.service`.

- API base URL: `http://<this machine>:8001/v1`. Any API key works.
- Browser chat: `http://<this machine>:8001/`
- Models:
  - `inkling-2-mini`: thinks at the chat template's default effort (0.9).
  - `inkling-2-mini-chat`: the lowest thinking effort ("none"; the model still writes a short thinking part).
- `"reasoning_effort"`: none, minimal, low, medium, high, xhigh, max, or a number 0-0.99.
- The thinking text arrives as `reasoning_content`; the answer as `content`. Tool calls, streaming, `stop`
  strings and `/v1/completions` work.
- Answers are the model's own best (greedy) text. Guessing only makes them faster; the answers are exactly the same
  as without it. Sampling settings are ignored.

## One conversation at a time

The engine keeps the latest conversation on the card:
- A follow-up turn only reads the new words, even after hundreds of thousands of tokens.
- A different conversation starts over in a few milliseconds and is read from the start (about 1,000 tokens/s
  short, ~330 tokens/s past 500K), unless the library has a saved start for it.
- A second client waits until the first answer is done.

## The library: long documents read once

`POST /admin/prefill {"name": "mydoc", "messages": [{"role": "system", "content": "<the document>"}]}` reads the
messages and saves the result to `/mnt/fast-ai/inkling-cache/lib/mydoc.inkc`. Every later conversation that starts
with exactly those messages (same `reasoning_effort` / model name) then loads it in seconds and reads only what
follows. A 22K-token document: read 23 s, loaded 0.3-0.4 s. A 515K-token prompt: read 25.5 minutes, loaded 3.2 s
(17.2 GB at 5.4 GB/s).
- `POST /admin/save {"name": ...}` saves the conversation the engine holds right now.
- `GET /admin/library` lists the saved prompts. Delete a file there to forget it.
- Saved prompts belong to this engine build's model file; one loads into any context size.

## Starting and stopping

- By hand: `/home/steve/dsv41-serve/venv/bin/python -I /home/steve/inkling-serve/server.py` (uses the DeepSeek
  server's Python environment: aiohttp + jinja2). The model loads in ~4 s.
- As a service: `sudo cp systemd/inkling-server.service /etc/systemd/system/ && sudo systemctl daemon-reload &&
  sudo systemctl enable --now inkling-server`.
- `GET /health` shows the state and the held conversation's length.
- The server runs on the card in `config.json` (`card`, default 1) through the lab's `on-card.sh`, which holds that
  card's lock: research jobs cannot use the card meanwhile, and the server does not start while the DeepSeek server
  holds the cards.
- Context size: `ctx_tiers` in `config.json` (default 65,536 / 131,072 / 300,000 / 515,000). The engine runs at the
  smallest size that holds the conversation plus its answer (`max_tokens`, default 32,768): smaller sizes read
  prompts in bigger steps (faster; 31K: ~970 vs ~816 tokens/s at the largest). A conversation that outgrows the size
  is saved, the engine restarts larger (~4 s) and loads it back, so only the new words are read; the answer is the
  same as without the change (checked). A new conversation of 8,192+ tokens that fits a smaller size restarts the
  engine smaller (`shrink_min_prompt`). 515,000 is the largest with the drafter (one card holds 530,000 without).

Files:
- `config.json`: engine settings, card, context, port.
- `server.py`: the API server (adapted from `/home/steve/dsv41-serve/server.py`).
- `bin/ink_run`: the engine (built from `b70-optimization-lab/experiments/own-xpu-runtime/inkling2`, `INK_SERVE=1`).
- `bin/tokhelper`: the tokenizer (llama.cpp Unsloth release b12588-mix, vocabulary only).
- `chat_template.jinja`: the model's template, taken from the GGUF.
- `logs/`: the logs.
