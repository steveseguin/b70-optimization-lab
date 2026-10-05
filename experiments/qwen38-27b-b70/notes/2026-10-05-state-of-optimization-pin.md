# Where the 27B optimization work stands (pinned 2026-10-05 01:30 EDT)

The owner asked to put a pin in this work and turn to context length. This is the state to resume from.

## Results, all exact by construction on two cards

Speed in tokens a second, all users together, short prompts; every run identical to a lone user on long and short
prompts and to the frozen single-user reference.

| Users at once | Drafting on | Drafting off | Run this |
| ---: | ---: | ---: | --- |
| 1 | **90** | 34 | drafting on |
| 2 | **138** | 65 | drafting on |
| 4 | **227** | 125 | drafting on |
| 8 | **336** | 236 | drafting on |
| 16 | 414 to 434 | 419 | either |
| 32 | not run | **657** | drafting off |
| 64 | not run | **874** | drafting off |

Long prompts (2K to 8K tokens) together: 50 to 58 tok/s with drafting on, 34 to 67 with it off (prompt reading
dominates). One user with longer copy drafts: +10 to +17 % on long prompts, 3 % slower on short ones.

## What makes it exact (each measured by a kernel census, data in `data/2026-10-04-kernel-census/`)

- Main FP8 layers: row-invariant for 1 to 512 rows. Normalisation as compiled: 1 to 512 rows. Output layer: 1 to 32
  rows, and the image works in 32-row pieces. Small FP16 projection: always the padded path, identical to 512 rows.
- Attention while writing: batch-invariant to 1,645-token contexts; longer ones get one call per conversation
  (`b70-fa-decode-per-seq`). Attention while checking drafts: identical to plain decoding for up to 6 rows at every
  tested length (10 rows with the overlay limit raised; 17 rows never).
- Recurrent kernel while writing: batch-invariant to 64 users. While checking drafts: bit-identical to plain decoding
  only on image **R313 or later** (eight-line kernel fix).
- Prompt reading across users: attention and recurrent kernels identical to reading alone (to 2,434 tokens).

## The pieces (all research overlays under `overlays/`, images local only)

| Piece | What it does | Needed for |
|---|---|---|
| Image **R314** (R310 + two kernel patches, `patches/*r313*`, `*r314*`) | drafting kernel equal to plain decoding; state table can be handed wide | everything with drafting |
| `b70-exclusive-prefill` (+ `BATCH=8`) | each step is prompt reading or writing, never both; several short prompts per reading step inside census limits | many users |
| `b70-fa-decode-per-seq` | one attention call per long conversation | many users |
| `b70-gdn-state-width` | no out-of-range state read when a step is narrower than the tokens just accepted | drafting (context edge, long drafts, many users) |
| `b70-spec-resume-accepted` | a request that sat out a step keeps its accepted-token count | drafting with many users |
| `b70-copy-draft` (`K_MAX`, synchronous pipeline) | copied text as a longer draft when available | long-context single user |
| `b70-chunked-upload` | no transfer of 512 MiB or more in one go (the model-load GPU fault) | shipped in both packages |

Dropped: `b70-lm-head-chunk` (never needed), the image's serial-exact switches (dead or three times slower),
copy drafts at depth 5 (no gain), reading two long prompts in one step (not exact).

## Not done (the packaging debt)

1. **The published packages are still on R310/R312d-c.** Their single-user drafting is identical on every test but
   not by construction. Moving them needs R314 pushed to the registry and a fresh acceptance each; the one-card
   package's kernel variant (`gdn_attention_ckpt`) needs the same eight-line fix first.
2. **No many-users package profile exists.** The table above is from research servers.
3. **The out-of-range state read exists in the published recipe at the very end of the context window** (rare; fixed
   by R314 + `b70-gdn-state-width`).
4. Second fresh servers are owed for: drafting at 2, 8 and 16 users; drafting off at 2, 4 and 8.
5. Returning requests lose their drafts for one step (speed only). Longer copy drafts want a larger long-context
   suite to choose the depth, and a port to the asynchronous pipeline to recover 2.3 %.
6. Upstream: the two engine bugs found here (state-table read past its end; accepted count lost when a request sits
   out a step) are worth reporting to vLLM, with the owner's approval.

Receipts: `data/2026-10-04-fp8-multiuser/`, `data/2026-10-04-r313/`, `data/2026-10-04-r314/`,
`data/2026-10-04-copy-draft/`, `data/2026-10-04-kernel-census/`. Test records: `notes/2026-10-04-fp8-multiuser-prereg.md`,
`notes/2026-10-04-speculation-not-exact-by-construction.md`, `notes/2026-10-04-copy-draft-sizing-prereg.md`.
