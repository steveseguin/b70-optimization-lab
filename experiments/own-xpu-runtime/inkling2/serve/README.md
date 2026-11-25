# Inkling-2-Mini LAN server

Inkling-2-Mini runs with our own engine, one copy per card (cards 1-5 by default; the model fits on one card). It
speaks the OpenAI API on port 8001. Not installed as a
service yet: start it by hand (below) or install `systemd/inkling-server.service`.

- API base URL: `http://<this machine>:8001/v1`. Any API key works.
- Browser chat: `http://<this machine>:8001/`
- Models:
  - `inkling-2-mini`: thinks at the chat template's default effort (0.9).
  - `inkling-2-mini-chat`: the lowest thinking effort ("none"; the model still writes a short thinking part).
- `"reasoning_effort"`: none, minimal, low, medium, high, xhigh, max, or a number 0-0.99.
- The thinking text arrives as `reasoning_content`; the answer as `content`. Tool calls, streaming, `stop`
  strings and `/v1/completions` work.
- Pictures: image parts in user (or tool) messages, as base64: OpenAI `{"type": "image_url", "image_url": {"url":
  "data:image/png;base64,..."}}`, Responses `input_image`, or Anthropic `{"type": "image", "source": {"type":
  "base64", ...}}` (web addresses are not fetched). The server decodes them (Pillow: RGB, alpha dropped), resizes a
  picture only if it would give more than 4,096 rows (the reference's rule: about 6.5 million pixels), and the
  engine encodes it on the card (Unsloth's `mmproj-BF16.gguf`, `INK_VISION` in `engine_env`): one row per 40 x 40
  pixel block (a 1024 x 768 photo is 520 rows of context). A card keeps a picture's rows while it is in use, so a
  follow-up question reads only the new text. Checked: the same answers as the reference (llama.cpp's image path in
  its high-precision mode, 100/100 greedy tokens on a test card) and as a server without state copies (8/8: card,
  follow-up, Anthropic format, photo, two pictures, a 4000 x 3000 photo, sampled, web address refused). The image
  encoder takes 1.07 GiB of card memory and is left out when the context tier leaves no room (515K): pictures are
  then refused with a message. The chat page takes pictures by paste, drop or its Picture button. Timings add `pictures_encoded` and `picture_s` (0.04 s for a 640 x 360 picture,
  3.3 s for the largest).
- Several conversations per card: `"seqs_per_card": 4` in config.json runs one engine per card holding 4
  conversations (each card then serves up to 4 requests at once; answers are the same as one at a time). They share
  one context size, `seq_ctx` (default the smallest of `ctx_tiers`), which does not grow; prompts are read in steps of
  `seq_ubatch` (896) tokens. Guessing, the drafter, saved prompts and /admin/save are off in this mode. A card holds 4
  conversations of 16K in 18.6 GiB; 8 requests on 2 cards x 4 took 6.4 s against 13.5 s one by one. Default 1 (one
  conversation per card, with guessing and context growth up to 515K).
- Thinking budget: `"thinking_budget": N` (also `max_thinking_tokens`, `chat_template_kwargs.thinking_budget`, or
  Anthropic-style `"thinking": {"type": "enabled", "budget_tokens": N}`; default `"thinking_budget"` in `config.json`,
  none). After N thinking tokens the server ends the thinking part and starts the answer (it adds `<|end_message|>
  <|message_model|><|content_text|>`; the engine reads those 3 tokens and goes on), so a long or looping think cannot
  use up `max_tokens`. `timings.thinking_cut` says whether it cut. Below the budget the answer is the same as without
  one (checked; and a cut answer is the same on a second server).
- Sampling: `temperature`, `top_p`, `top_k`, `min_p`, `seed`. Unset ones take the model file's recommended values
  (`general.sampling.*`: temperature 1.0, top_p 1.0, top_k 0, min_p 0.0; `"sampling"` in `config.json` overrides).
  `temperature: 0` gives the most likely token at every step. The engine samples from the model's exact scores with a
  random number taken from (seed, position): the same conversation, settings and seed give the same answer every
  time, and guessing only makes it faster (checked: identical text with and without guessing). Without a `seed` each
  request draws one; `timings.sampling` returns it. Temperature 1.0 matters with this model: always taking the most
  likely token sometimes makes it think in circles until `max_tokens` (the model card warns about reasoning loops;
  in a 480K-token recall test 4 of 21 questions ended that way although the model had found the answers).

## One conversation per card

Each card's engine keeps the latest conversation it answered:
- A follow-up goes back to the card holding its conversation and only reads the new words, even after hundreds of
  thousands of tokens.
- A new conversation goes to a free card (an empty one first, then the one used least recently). It is read from
  the start (about 1,000 tokens/s short, ~330 tokens/s past 500K), unless the library has a saved start for it.
- Five cards answer five conversations at the same time; a sixth waits for a card.
- The server remembers its recent answers in full (thinking included; `known_answers_max_chars`, 64 MB) and puts
  them back when a client sends the conversation again without the thinking, so a follow-up reads the same on any
  card. An answer depends only on its conversation, not on which card ran it or what else was asked meanwhile
  (checked: two cards at once, and one card switching between two conversations, gave the same thinking and
  answers as one conversation at a time).
- Each engine also keeps two copies of the state that later text overwrites (the windowed attention rings, short
  convolutions and drafter state, ~1.4 GiB each at the 64K size, ~0.3 GiB at 300K, none at 515K where the card is
  full): one at the start of the last request's last message and one at the start of the conversation's first
  message after the system messages. A regenerated answer, an edited last message, another question after the same
  document or a new conversation with the same system prompt (and tools and effort) continues from a copy in ~0.02 s
  and reads only what follows it (checked against an engine without copies: 13 of 13 answers identical; an
  8,719-token document's next question read 11 tokens in 0.07 s instead of 8.8 s). Requests go to the card whose
  conversation shares the longest start with them (`share_min_bytes`, `share_wait_bytes`).
- Host memory: about 1.3 GB per engine at any context size (five engines up: 7.6 GB of 15 GB still available).
- Checked under load: 8 clients x 3 turns on 5 cards (streaming and not, a stop string, the default thinking effort,
  a client that dropped its stream mid-answer and asked again): 12.1 s instead of 37.3 s one at a time, and all 24
  answers identical to a fresh one-card server answering each conversation alone.
- Tool calls (checked, streamed and not, same results): asked for the weather in two cities with two tools offered,
  the model called `get_weather` twice in one answer (`finish_reason` "tool_calls"), then answered from the results;
  the second request read only the tool results (387 of 456 tokens cached).

## The library: long documents read once

`POST /admin/prefill {"name": "mydoc", "messages": [{"role": "system", "content": "<the document>"}]}` reads the
messages and saves the result to `/mnt/fast-ai/inkling-cache/lib/mydoc.inkc`. Every later conversation that starts
with exactly those messages (same `reasoning_effort` / model name) then loads it in seconds and reads only what
follows. A 22K-token document: read 23 s, loaded 0.3-0.4 s. A 515K-token prompt: read 25.5 minutes, loaded 3.2 s
(17.2 GB at 5.4 GB/s).
- `POST /admin/save {"name": ..., "card": n}` saves the conversation a card holds right now (default: the card used
  last).
- `GET /admin/library` lists the saved prompts. Delete a file there to forget it.
- Saved prompts belong to this engine build's model file; one loads into any context size.

## Starting and stopping

- By hand: `/home/steve/dsv41-serve/venv/bin/python -I /home/steve/inkling-serve/server.py` (uses the DeepSeek
  server's Python environment: aiohttp + jinja2). The model loads in ~4 s.
- As a service: `sudo cp systemd/inkling-server.service /etc/systemd/system/ && sudo systemctl daemon-reload &&
  sudo systemctl enable --now inkling-server`.
- `GET /health` shows each card's state, context size and held conversation length.
- The server runs on the cards in `config.json` (`cards`, default 1-5; fewer leaves cards free for other work),
  each through the lab's `on-card.sh`, which holds that card's lock: research jobs cannot use the card meanwhile,
  and the server does not start while the DeepSeek server holds the cards. The engines load one after another
  (~4 s each).
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
- `logs/`: the logs (`engine-c<card>-*.log` per engine).
