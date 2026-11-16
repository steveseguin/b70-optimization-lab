# lc1: the first prompt past 95K tokens - 194,000 tokens, exact in two modes, the planted fact found (2026-11-15 19:36)

Configuration: the current diagnostic setup (SMT off, Gen4 x16 root links, `OWN_PX_SERIAL=1`, default power, BIOS
11.02; `stable/preflight.sh` before each start). Existing tp115 binary (sha256 45f72213174a60c2). Script `lc1.sh`.

Prompt: a chat request over 700,000 characters of this repo's docs + DeepSeek notes (`mk_needle.py`, document sha256
de6921f3b90e788c, ids e3093a3331f3f776) with one planted sentence at 2 % of the text ("the access code for the
archive room is 7194-KESTREL"); the request asks for the code first, then five rules. 194,000 tokens, 1024 plain
answer tokens, max context 195,584.

| run | prompt reading | writing at ~195K | free card memory after load (card 2, the least) |
|---|---|---|---|
| production prompt mode | **300.69 s (645.2 tok/s)** | **87.72 tok/s** | 2.00 GiB |
| tp115 switches off (`OWN_SKIP39=0 OWN_IDX_DSPLIT=0`) | 308.30 s (629.2 tok/s) | 85.29 tok/s | 2.00 GiB |

- The two runs' 1024 answer tokens are identical (`summary.txt`: IDS1024_SAME); no fault line, both exits 0.
- The answer (`x200k_def-answer.txt`) finds the planted code: "It appears in MiniMax deployment section: 'Note for the
  reader: the access code for the archive room is 7194-KESTREL.'" (the sentence sits at 2 % of the document; the model
  names the right neighbouring section).
- Reading speed holds at long context: 645 tok/s at 194K against 682 at 3K and ~661 at 95K (c115, same mode).
- Card memory: ~6.2 KB per context token per card (linear from 4K to 195K); 2.00 GiB still free on card 2.
- Host memory: the 175 GB weight upload takes ~10 GB of MemAvailable for ~20 s (12,882 -> 2,789 MiB minimum, `mem.txt`
  in the run folder), independent of context length. The first attempt (`first-attempt-summary.txt`, 19:34) stopped
  safely at the engine's default 3,072 MiB floor because it started ~1 GB lower than usual; lc1 uses
  `OWN_HOST_FLOOR_MIB=2560`.
