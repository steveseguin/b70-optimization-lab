# Rollback and context buckets

Target rank0 may append one speculative half. Recurrent convolution/GDN state
uses the existing alternate bank. QSA keys, values, raw index and completed
pooled index are append-only: earlier valid positions are never overwritten.
Rollback restores the logical position, recurrent bank, history and lookup
validity. The rejected append remains outside the valid prefix and the redo
writes it before selection. It therefore requires no capacity-sized cache copy.
The draft only consumes confirmed target halves; no draft KV rollback is needed.

Each bank carries the launch extent belonging to its prepared commands. Swapping
banks swaps that extent too. Before every half, admit_position checks the logical
position and refreshes only select/attention sites if the 32-position bucket
changed. This also handles redo after a rejected cross-boundary speculation and
request reset back to zero. A kernel independently rejects a position beyond
its captured extent. Bucket extent is never a reduction length or capacity
stride. The draft has a separate position and refreshes its own affected sites.

The CPU boundary gate uses a 31-token prompt, an intentionally wrong guess at
position32 and the actual prepared resident miniature. It requires the rejected
half to use extent64 and checks tokens, all retained layers and valid state
against sequential execution. CPU evidence is a gate, not device qualification.
