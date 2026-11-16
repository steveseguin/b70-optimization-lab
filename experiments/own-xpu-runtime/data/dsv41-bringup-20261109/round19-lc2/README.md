# lc2: 388,251 tokens - exact in two modes, the planted fact found (2026-11-15 19:48-20:11)

Same configuration and method as round19-lc1 (diagnostic setup: SMT off, Gen4 x16, `OWN_PX_SERIAL=1`, default power,
BIOS 11.02; tp115 binary 45f72213174a60c2; `OWN_HOST_FLOOR_MIB=2560`). Prompt: `doc2.txt` = lc1's document + 175
experiments / packages READMEs of this repo (sha256 253d12f344335ffe), cut at 1,375,000 characters, the same planted
sentence at 2 % (ids aff7f0bc3a8f3bee). 388,251 tokens, 1024 plain answer tokens, max context 390,144.

| run | prompt reading | writing at ~389K | free card memory after load (card 2) |
|---|---|---|---|
| production prompt mode | **633.22 s (613.1 tok/s)** | **76.90 tok/s** | 0.86 GiB |
| tp115 switches off (`OWN_SKIP39=0 OWN_IDX_DSPLIT=0`) | 647.78 s (599.3 tok/s) | 70.77 tok/s | 0.87 GiB |

- 1024 answer tokens identical across the two runs (IDS1024_SAME); exits 0; no fault line.
- The answer (`x400k_def-answer.txt`) states "Access code: **7194-KESTREL**" and lists the five gates of the section
  the sentence was planted in (benchmark integrity audit), a coherent answer over 388K tokens.
- Reading speed: 682 (3K) / 661 (95K) / 645 (194K) / 613 tok/s (388K): -10 % from 3K to 388K.
- Writing: 98.6 (after 3K) / 87.7 (195K) / 76.9 tok/s (389K).
- Card memory per context token and card: (2.00 - 0.86) GiB / 194,560 tokens = **~6.3 KB** (card 2, lc1 -> lc2).
  At the load guard's 384 MiB margin the current build's ceiling is about **465K tokens** of context (card 2).
  Where the 6.3 KB goes (source, tp115): the prompt-block index scores + candidate marks, 512 block tokens x (4 + 1)
  bytes = 2,560 B; the compressed-KV mirrors (4 sources, 2.5 rows per token x 512 dims x 2 B) 2,560 B; the index-key
  mirrors 2.5 x 128 x 2 B = 640 B; the rest ~0.5 KB.
